#!/usr/bin/env python3
"""Main entry point for SKY13 Trade Engine."""

import logging
import sys
from datetime import datetime
from config import config
from database import db
from broker_iifl import broker
from telegram_bot import TelegramBot
from ema_engine import EMAEngine
from trading_engine import TradingEngine
from risk_manager import RiskManager
from signal_filter import SignalFilter

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.logging.level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{config.logging.log_path}/trade_engine.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class SKY13TradeEngine:
    """Main Trade Engine class."""
    
    def __init__(self):
        """Initialize the trade engine."""
        logger.info('Initializing SKY13 Trade Engine')
        
        # Validate configuration
        try:
            config.validate()
        except ValueError as e:
            logger.error(f'Configuration validation failed: {e}')
            sys.exit(1)
        
        # Initialize components
        self.telegram = TelegramBot()
        self.ema_engine = EMAEngine(config.trading.symbol)
        self.trading_engine = TradingEngine(config.trading.symbol)
        self.risk_manager = RiskManager()
        self.signal_filter = SignalFilter()
        
        self.is_running = False
        logger.info('SKY13 Trade Engine initialized successfully')
    
    def start(self) -> bool:
        """Start the trade engine.
        
        Returns:
            True if started successfully
        """
        logger.info('Starting SKY13 Trade Engine')
        
        try:
            # Connect to broker
            if not broker.login():
                logger.error('Failed to login to broker')
                self.telegram.send_startup_message('FAILED')
                return False
            
            # Download historical candles for EMA warm-up
            logger.info('Downloading historical candles...')
            candles = broker.get_candles(
                symbol=config.trading.symbol,
                timeframe=config.trading.timeframe,
                days_back=30
            )
            
            if candles:
                logger.info(f'Downloaded {len(candles)} candles')
                for candle in candles:
                    self.ema_engine.add_candle(candle['close'], candle.get('volume', 0))
            else:
                logger.warning('No historical candles downloaded')
            
            # Check existing positions
            positions = broker.get_positions()
            logger.info(f'Found {len(positions)} existing positions')
            
            self.is_running = True
            self.telegram.send_startup_message('SUCCESS')
            logger.info('✅ SKY13 Trade Engine started successfully')
            return True
        
        except Exception as e:
            logger.error(f'Failed to start trade engine: {e}')
            self.telegram.send_startup_message('FAILED')
            return False
    
    def stop(self):
        """Stop the trade engine."""
        logger.info('Stopping SKY13 Trade Engine')
        try:
            broker.logout()
            self.is_running = False
            logger.info('✅ SKY13 Trade Engine stopped')
        except Exception as e:
            logger.error(f'Error stopping engine: {e}')
    
    def process_tick(self):
        """Process a market tick."""
        try:
            if not self.is_running:
                return
            
            # Get current price
            price = broker.get_ltp(config.trading.symbol)
            if not price:
                logger.warning(f'Failed to get LTP for {config.trading.symbol}')
                return
            
            # Add candle to EMA engine
            self.ema_engine.add_candle(price)
            
            # Check for signals
            signal = self.ema_engine.get_signal(price)
            
            if signal:
                logger.info(f'Signal detected: {signal}')
                
                # Apply filters
                if self.signal_filter.apply_filters(
                    signal,
                    self.ema_engine.current_ema_fast,
                    self.ema_engine.current_ema_slow,
                    current_time=datetime.now()
                ):
                    # Check risk constraints
                    if self.risk_manager.can_trade():
                        # Execute trade
                        self._execute_signal(signal, price)
                        self.signal_filter.update_reversal_time(datetime.now())
                    else:
                        logger.warning('Trading stopped due to risk constraints')
                        self.telegram.send_error_alert('Daily loss limit exceeded')
                else:
                    logger.info(f'{signal} signal filtered out')
        
        except Exception as e:
            logger.error(f'Error processing tick: {e}')
            self.telegram.send_error_alert(str(e))
    
    def _execute_signal(self, signal: str, price: float):
        """Execute a trading signal.
        
        Args:
            signal: BUY or SELL
            price: Current price
        """
        try:
            logger.info(f'Executing {signal} signal at {price}')
            
            # Close existing position if signal is opposite
            open_pos = self.trading_engine.get_position_summary()
            if open_pos and open_pos['side'] != signal:
                logger.info(f'Closing opposite position before new {signal}')
                self.trading_engine.close_position(open_pos['trade_id'])
            
            # Open new position
            trade_id = self.trading_engine.open_position(
                side=signal,
                quantity=config.trading.quantity,
                price=price,
                ema_fast=self.ema_engine.current_ema_fast,
                ema_slow=self.ema_engine.current_ema_slow
            )
            
            if trade_id:
                self.telegram.send_trade_alert(
                    signal,
                    config.trading.symbol,
                    price,
                    self.ema_engine.current_ema_fast,
                    self.ema_engine.current_ema_slow
                )
        
        except Exception as e:
            logger.error(f'Error executing signal: {e}')
            self.telegram.send_error_alert(f'Signal execution failed: {e}')
    
    def run(self):
        """Run the trade engine (main loop)."""
        if not self.start():
            logger.error('Failed to start engine')
            return
        
        try:
            logger.info('Entering main trading loop')
            # TODO: Implement main trading loop with websocket/polling
            # This is a placeholder - implement actual market data streaming
            while self.is_running:
                self.process_tick()
        
        except KeyboardInterrupt:
            logger.info('Interrupted by user')
        except Exception as e:
            logger.error(f'Unexpected error in main loop: {e}')
        finally:
            self.stop()


def main():
    """Main entry point."""
    engine = SKY13TradeEngine()
    engine.run()


if __name__ == '__main__':
    main()
