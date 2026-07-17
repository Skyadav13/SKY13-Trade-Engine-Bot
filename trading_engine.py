"""Trading Engine for SKY13 Trade Engine."""
import logging
from typing import Dict, Optional, List
from datetime import datetime
from config import config
from database import db
from broker_iifl import broker

logger = logging.getLogger(__name__)


class TradingEngine:
    """Main Trading Engine - Manages positions and orders."""
    
    def __init__(self, symbol: str):
        """Initialize Trading Engine.
        
        Args:
            symbol: Trading symbol
        """
        self.symbol = symbol
        self.current_position = None
        self.pending_orders = {}
    
    def open_position(self, side: str, quantity: int, price: float,
                     ema_fast: float, ema_slow: float, rsi_value: float = None) -> Optional[str]:
        """Open a new position.
        
        Args:
            side: BUY or SELL
            quantity: Order quantity
            price: Entry price
            ema_fast: Fast EMA value
            ema_slow: Slow EMA value
            rsi_value: RSI value (optional)
        
        Returns:
            Trade ID or None if failed
        """
        # Check if already have an open position
        if self.current_position:
            logger.warning(f'Already have open position for {self.symbol}')
            return None
        
        try:
            # Close any existing position first
            open_positions = db.get_open_positions(self.symbol)
            if open_positions:
                logger.info(f'Closing {len(open_positions)} existing positions before opening new one')
                for pos in open_positions:
                    self.close_position(pos['trade_id'])
            
            # Place order via broker
            order_response = broker.place_order(
                symbol=self.symbol,
                side=side,
                quantity=quantity,
                price=price
            )
            
            if not order_response:
                logger.error(f'Failed to place {side} order for {self.symbol}')
                return None
            
            order_id = order_response.get('order_id')
            
            # Create trade record
            trade_id = f'TRD_{datetime.now().timestamp()}'
            trade_data = {
                'trade_id': trade_id,
                'symbol': self.symbol,
                'side': side,
                'instrument': config.trading.instrument,
                'price': price,
                'quantity': quantity,
                'entry_time': datetime.now(),
                'ema_fast': ema_fast,
                'ema_slow': ema_slow,
                'rsi_value': rsi_value
            }
            
            db.insert_trade(trade_data)
            
            # Record order
            order_data = {
                'order_id': order_id,
                'trade_id': trade_id,
                'symbol': self.symbol,
                'side': side,
                'price': price,
                'quantity': quantity,
                'order_time': datetime.now()
            }
            
            db.insert_order(order_data)
            self.pending_orders[order_id] = trade_id
            
            logger.info(f'Opened {side} position: {trade_id} via order {order_id}')
            return trade_id
        
        except Exception as e:
            logger.error(f'Error opening position: {e}')
            return None
    
    def close_position(self, trade_id: str) -> bool:
        """Close an existing position.
        
        Args:
            trade_id: Trade ID to close
        
        Returns:
            True if successful
        """
        try:
            # Get position details
            open_positions = db.get_open_positions(self.symbol)
            position = None
            for pos in open_positions:
                if pos['trade_id'] == trade_id:
                    position = pos
                    break
            
            if not position:
                logger.warning(f'Position {trade_id} not found')
                return False
            
            # Place opposite order
            opposite_side = 'SELL' if position['side'] == 'BUY' else 'BUY'
            order_response = broker.place_order(
                symbol=self.symbol,
                side=opposite_side,
                quantity=position['quantity'],
                price=0  # Market order
            )
            
            if order_response:
                # Update trade status
                profit_loss = self._calculate_profit_loss(position)
                db.update_trade_status(trade_id, 'CLOSED', datetime.now(), profit_loss)
                logger.info(f'Closed position {trade_id}: P&L = {profit_loss}')
                return True
            else:
                logger.error(f'Failed to place closing order for {trade_id}')
                return False
        
        except Exception as e:
            logger.error(f'Error closing position: {e}')
            return False
    
    def _calculate_profit_loss(self, position: Dict) -> float:
        """Calculate profit/loss for a position.
        
        Args:
            position: Position dictionary
        
        Returns:
            Profit/Loss amount
        """
        # TODO: Get current price and calculate actual P&L
        current_price = broker.get_ltp(self.symbol)
        if current_price:
            if position['side'] == 'BUY':
                pl = (current_price - position['price']) * position['quantity']
            else:
                pl = (position['price'] - current_price) * position['quantity']
            return pl
        return 0.0
    
    def verify_order_filled(self, order_id: str, timeout_seconds: int = 40) -> bool:
        """Verify if an order is filled.
        
        Args:
            order_id: Order ID
            timeout_seconds: Timeout in seconds
        
        Returns:
            True if filled
        """
        order_status = broker.get_order_status(order_id)
        return order_status.get('status') == 'FILLED'
    
    def get_position_summary(self) -> Optional[Dict]:
        """Get summary of current position.
        
        Returns:
            Position summary or None
        """
        positions = db.get_open_positions(self.symbol)
        if positions:
            pos = positions[0]  # Only one position allowed
            return {
                'trade_id': pos['trade_id'],
                'symbol': pos['symbol'],
                'side': pos['side'],
                'quantity': pos['quantity'],
                'entry_price': pos['price'],
                'entry_time': pos['entry_time'],
                'current_pl': self._calculate_profit_loss(pos)
            }
        return None
