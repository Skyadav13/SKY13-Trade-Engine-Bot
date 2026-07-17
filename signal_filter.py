"""Signal Filters for SKY13 Trade Engine."""
import logging
from typing import Dict, List
from config import config

logger = logging.getLogger(__name__)


class SignalFilter:
    """Filter EMA signals to reduce false positives."""
    
    def __init__(self):
        """Initialize signal filter."""
        self.last_reversal_time = None
        self.filter_results = {}
    
    def check_ema_separation(self, ema_fast: float, ema_slow: float) -> bool:
        """Check if EMA separation is sufficient.
        
        Args:
            ema_fast: Fast EMA value
            ema_slow: Slow EMA value
        
        Returns:
            True if separation is sufficient
        """
        if ema_fast is None or ema_slow is None:
            return False
        
        separation_percent = abs((ema_fast - ema_slow) / ema_slow * 100)
        min_sep = config.risk.min_ema_separation
        
        self.filter_results['ema_separation'] = {
            'passed': separation_percent >= min_sep,
            'value': separation_percent,
            'required': min_sep
        }
        
        return separation_percent >= min_sep
    
    def check_cooldown(self, current_time) -> bool:
        """Check if cooldown period has passed since last reversal.
        
        Args:
            current_time: Current time
        
        Returns:
            True if cooldown has passed or no previous reversal
        """
        if self.last_reversal_time is None:
            return True
        
        time_diff = (current_time - self.last_reversal_time).total_seconds()
        passed = time_diff >= config.risk.sideways_cooldown
        
        self.filter_results['cooldown'] = {
            'passed': passed,
            'seconds_elapsed': time_diff,
            'required': config.risk.sideways_cooldown
        }
        
        return passed
    
    def check_rsi_filter(self, rsi_value: float, signal_type: str) -> bool:
        """Check RSI filter (optional).
        
        Args:
            rsi_value: Current RSI value
            signal_type: BUY or SELL
        
        Returns:
            True if RSI filter passes
        """
        if rsi_value is None:
            return True
        
        if signal_type == 'BUY':
            # For BUY, RSI should not be too high (oversold)
            passed = rsi_value < config.rsi.overbought
        elif signal_type == 'SELL':
            # For SELL, RSI should not be too low (overbought)
            passed = rsi_value > config.rsi.oversold
        else:
            passed = True
        
        self.filter_results['rsi'] = {
            'passed': passed,
            'value': rsi_value,
            'signal': signal_type
        }
        
        return passed
    
    def check_trend_filter(self, adx_value: float) -> bool:
        """Check ADX trend filter (optional).
        
        Args:
            adx_value: Current ADX value
        
        Returns:
            True if trend is strong enough
        """
        if adx_value is None:
            return True
        
        threshold = config.adx.trend_threshold
        passed = adx_value >= threshold
        
        self.filter_results['trend'] = {
            'passed': passed,
            'value': adx_value,
            'threshold': threshold
        }
        
        return passed
    
    def apply_filters(self, signal_type: str, ema_fast: float, ema_slow: float,
                     rsi_value: float = None, adx_value: float = None,
                     current_time = None) -> bool:
        """Apply all filters to a signal.
        
        Args:
            signal_type: BUY or SELL
            ema_fast: Fast EMA value
            ema_slow: Slow EMA value
            rsi_value: RSI value (optional)
            adx_value: ADX value (optional)
            current_time: Current time for cooldown check
        
        Returns:
            True if all filters pass
        """
        self.filter_results = {}
        
        filters_passed = True
        
        # EMA Separation filter (required)
        if not self.check_ema_separation(ema_fast, ema_slow):
            filters_passed = False
            logger.debug(f'EMA separation filter failed')
        
        # Cooldown filter (required)
        if current_time and not self.check_cooldown(current_time):
            filters_passed = False
            logger.debug(f'Cooldown filter failed')
        
        # RSI filter (optional)
        if rsi_value is not None:
            if not self.check_rsi_filter(rsi_value, signal_type):
                logger.debug(f'RSI filter failed for {signal_type}')
        
        # Trend filter (optional)
        if adx_value is not None:
            if not self.check_trend_filter(adx_value):
                logger.debug(f'Trend filter failed')
        
        if filters_passed:
            logger.info(f'{signal_type} signal passed all filters')
        
        return filters_passed
    
    def update_reversal_time(self, current_time):
        """Update the last reversal time.
        
        Args:
            current_time: Current time
        """
        self.last_reversal_time = current_time
    
    def get_filter_results(self) -> Dict:
        """Get detailed filter results.
        
        Returns:
            Dictionary of filter results
        """
        return self.filter_results
