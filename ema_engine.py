"""EMA Engine for SKY13 Trade Engine."""
import logging
from typing import List, Dict, Optional, Tuple
from collections import deque
from datetime import datetime
from config import config

logger = logging.getLogger(__name__)


class EMAEngine:
    """EMA Calculation and Signal Generation."""
    
    def __init__(self, symbol: str, fast_period: int = None, slow_period: int = None):
        """Initialize EMA Engine.
        
        Args:
            symbol: Trading symbol
            fast_period: Fast EMA period (default from config)
            slow_period: Slow EMA period (default from config)
        """
        self.symbol = symbol
        self.fast_period = fast_period or config.ema.fast_ema
        self.slow_period = slow_period or config.ema.slow_ema
        
        self.prices = deque(maxlen=self.slow_period * 2)
        self.ema_fast_values = deque()
        self.ema_slow_values = deque()
        
        self.current_ema_fast = None
        self.current_ema_slow = None
        self.is_warmed_up = False
        self.last_signal = None
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate EMA for a given period.
        
        Args:
            prices: List of prices
            period: EMA period
        
        Returns:
            EMA value
        """
        if len(prices) < period:
            return None
        
        # Simple Moving Average for the first point
        sma = sum(prices[-period:]) / period
        ema = sma
        
        multiplier = 2.0 / (period + 1)
        
        # Calculate EMA for subsequent prices
        for price in prices[-period+1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def add_candle(self, close_price: float, volume: int = 0) -> Tuple[Optional[float], Optional[float]]:
        """Add a new candle and update EMA.
        
        Args:
            close_price: Close price of the candle
            volume: Volume (optional)
        
        Returns:
            Tuple of (ema_fast, ema_slow)
        """
        self.prices.append(close_price)
        
        # Check if we have enough data for EMA calculation
        if len(self.prices) < self.slow_period:
            return None, None
        
        # Calculate EMAs
        self.current_ema_fast = self.calculate_ema(list(self.prices), self.fast_period)
        self.current_ema_slow = self.calculate_ema(list(self.prices), self.slow_period)
        
        # Store values
        self.ema_fast_values.append(self.current_ema_fast)
        self.ema_slow_values.append(self.current_ema_slow)
        
        # Check if warmed up
        if not self.is_warmed_up and len(self.ema_fast_values) > config.ema.warmup_candles:
            self.is_warmed_up = True
            logger.info(f'EMA Engine for {self.symbol} is warmed up')
        
        return self.current_ema_fast, self.current_ema_slow
    
    def get_signal(self, price: float) -> Optional[str]:
        """Get BUY/SELL signal based on EMA crossover.
        
        Args:
            price: Current price
        
        Returns:
            'BUY', 'SELL', or None
        """
        if not self.is_warmed_up or len(self.ema_fast_values) < 2:
            return None
        
        # Get current and previous EMA values
        curr_fast = self.ema_fast_values[-1]
        curr_slow = self.ema_slow_values[-1]
        prev_fast = self.ema_fast_values[-2] if len(self.ema_fast_values) > 1 else None
        prev_slow = self.ema_slow_values[-2] if len(self.ema_slow_values) > 1 else None
        
        if prev_fast is None or prev_slow is None:
            return None
        
        # BUY Signal: Fast EMA crosses above Slow EMA
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            signal = 'BUY'
            self.last_signal = signal
            logger.info(f'BUY signal for {self.symbol}: Fast EMA {curr_fast:.2f} > Slow EMA {curr_slow:.2f}')
            return signal
        
        # SELL Signal: Fast EMA crosses below Slow EMA
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            signal = 'SELL'
            self.last_signal = signal
            logger.info(f'SELL signal for {self.symbol}: Fast EMA {curr_fast:.2f} < Slow EMA {curr_slow:.2f}')
            return signal
        
        return None
    
    def get_state(self) -> Dict:
        """Get current EMA state for recovery.
        
        Returns:
            State dictionary
        """
        return {
            'symbol': self.symbol,
            'prices': list(self.prices),
            'ema_fast': self.current_ema_fast,
            'ema_slow': self.current_ema_slow,
            'is_warmed_up': self.is_warmed_up,
            'last_signal': self.last_signal,
            'timestamp': datetime.now().isoformat()
        }
    
    def restore_state(self, state: Dict):
        """Restore EMA state from recovery data.
        
        Args:
            state: State dictionary
        """
        if state['symbol'] != self.symbol:
            logger.warning(f'Symbol mismatch in recovery: {state["symbol"]} != {self.symbol}')
            return
        
        self.prices = deque(state['prices'], maxlen=self.slow_period * 2)
        self.current_ema_fast = state['ema_fast']
        self.current_ema_slow = state['ema_slow']
        self.is_warmed_up = state['is_warmed_up']
        self.last_signal = state['last_signal']
        
        logger.info(f'EMA state restored for {self.symbol}')
    
    def reset(self):
        """Reset EMA engine."""
        self.prices.clear()
        self.ema_fast_values.clear()
        self.ema_slow_values.clear()
        self.current_ema_fast = None
        self.current_ema_slow = None
        self.is_warmed_up = False
        self.last_signal = None
        logger.info(f'EMA Engine for {self.symbol} reset')
