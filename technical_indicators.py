"""Technical Indicators for SKY13 Trade Engine."""
import logging
from typing import List, Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class RSI:
    """Relative Strength Index indicator."""
    
    def __init__(self, period: int = 14):
        """Initialize RSI calculator.
        
        Args:
            period: RSI period (default 14)
        """
        self.period = period
        self.prices = deque(maxlen=period + 1)
        self.rsi_value = None
    
    def add_price(self, price: float) -> Optional[float]:
        """Add a new price and calculate RSI.
        
        Args:
            price: New price
        
        Returns:
            RSI value or None if not enough data
        """
        self.prices.append(price)
        
        if len(self.prices) < self.period + 1:
            return None
        
        prices_list = list(self.prices)
        gains = 0.0
        losses = 0.0
        
        # Calculate price changes
        for i in range(1, len(prices_list)):
            change = prices_list[i] - prices_list[i - 1]
            if change > 0:
                gains += change
            else:
                losses += abs(change)
        
        avg_gain = gains / self.period
        avg_loss = losses / self.period
        
        if avg_loss == 0:
            self.rsi_value = 100.0 if avg_gain > 0 else 0.0
        else:
            rs = avg_gain / avg_loss
            self.rsi_value = 100.0 - (100.0 / (1.0 + rs))
        
        return self.rsi_value
    
    def get_rsi(self) -> Optional[float]:
        """Get current RSI value.
        
        Returns:
            RSI value or None
        """
        return self.rsi_value
    
    def reset(self):
        """Reset RSI calculator."""
        self.prices.clear()
        self.rsi_value = None


class ATR:
    """Average True Range indicator."""
    
    def __init__(self, period: int = 14):
        """Initialize ATR calculator.
        
        Args:
            period: ATR period (default 14)
        """
        self.period = period
        self.true_ranges = deque(maxlen=period)
        self.atr_value = None
        self.first_atr = True
    
    def add_candle(self, high: float, low: float, close: float,
                   prev_close: float = None) -> Optional[float]:
        """Add a candle and calculate ATR.
        
        Args:
            high: High price of candle
            low: Low price of candle
            close: Close price of candle
            prev_close: Previous close price
        
        Returns:
            ATR value or None if not enough data
        """
        # Calculate true range
        tr1 = high - low
        tr2 = abs(high - prev_close) if prev_close else 0
        tr3 = abs(low - prev_close) if prev_close else 0
        true_range = max(tr1, tr2, tr3)
        
        self.true_ranges.append(true_range)
        
        if len(self.true_ranges) < self.period:
            return None
        
        # Calculate ATR
        if self.first_atr:
            self.atr_value = sum(self.true_ranges) / self.period
            self.first_atr = False
        else:
            self.atr_value = (self.atr_value * (self.period - 1) + true_range) / self.period
        
        return self.atr_value
    
    def get_atr(self) -> Optional[float]:
        """Get current ATR value.
        
        Returns:
            ATR value or None
        """
        return self.atr_value
    
    def reset(self):
        """Reset ATR calculator."""
        self.true_ranges.clear()
        self.atr_value = None
        self.first_atr = True


class ADX:
    """Average Directional Index indicator."""
    
    def __init__(self, period: int = 14):
        """Initialize ADX calculator.
        
        Args:
            period: ADX period (default 14)
        """
        self.period = period
        self.plus_dm_values = deque(maxlen=period)
        self.minus_dm_values = deque(maxlen=period)
        self.plus_di = None
        self.minus_di = None
        self.adx_value = None
        self.dx_values = deque(maxlen=period)
        self.first_adx = True
    
    def add_candle(self, high: float, low: float, close: float,
                   prev_high: float = None, prev_low: float = None,
                   prev_close: float = None, atr: float = None) -> Optional[float]:
        """Add a candle and calculate ADX.
        
        Args:
            high: High price
            low: Low price
            close: Close price
            prev_high: Previous high
            prev_low: Previous low
            prev_close: Previous close
            atr: ATR value for DI calculation
        
        Returns:
            ADX value or None if not enough data
        """
        if prev_high is None or prev_low is None:
            return None
        
        # Calculate directional movements
        plus_dm = max(high - prev_high, 0) if high > prev_high else 0
        minus_dm = max(prev_low - low, 0) if low < prev_low else 0
        
        # Apply directional rules
        if plus_dm > minus_dm:
            minus_dm = 0
        elif minus_dm > plus_dm:
            plus_dm = 0
        elif plus_dm == minus_dm and plus_dm > 0:
            plus_dm = 0
            minus_dm = 0
        
        self.plus_dm_values.append(plus_dm)
        self.minus_dm_values.append(minus_dm)
        
        if len(self.plus_dm_values) < self.period or atr is None or atr == 0:
            return None
        
        # Calculate DI values
        plus_di_raw = (sum(self.plus_dm_values) / atr) * 100
        minus_di_raw = (sum(self.minus_dm_values) / atr) * 100
        
        self.plus_di = plus_di_raw
        self.minus_di = minus_di_raw
        
        # Calculate DX
        di_sum = self.plus_di + self.minus_di
        if di_sum > 0:
            dx = (abs(self.plus_di - self.minus_di) / di_sum) * 100
            self.dx_values.append(dx)
        
        if len(self.dx_values) < self.period:
            return None
        
        # Calculate ADX
        if self.first_adx:
            self.adx_value = sum(self.dx_values) / self.period
            self.first_adx = False
        else:
            self.adx_value = (self.adx_value * (self.period - 1) + self.dx_values[-1]) / self.period
        
        return self.adx_value
    
    def get_adx(self) -> Optional[float]:
        """Get current ADX value.
        
        Returns:
            ADX value or None
        """
        return self.adx_value
    
    def get_plus_di(self) -> Optional[float]:
        """Get +DI value."""
        return self.plus_di
    
    def get_minus_di(self) -> Optional[float]:
        """Get -DI value."""
        return self.minus_di
    
    def reset(self):
        """Reset ADX calculator."""
        self.plus_dm_values.clear()
        self.minus_dm_values.clear()
        self.dx_values.clear()
        self.plus_di = None
        self.minus_di = None
        self.adx_value = None
        self.first_adx = True
