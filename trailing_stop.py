"""Trailing Stop Management for SKY13 Trade Engine."""
import logging
from typing import Optional, Dict
from config import config

logger = logging.getLogger(__name__)


class TrailingStop:
    """Trailing Stop management for RSI Smart Exit."""
    
    def __init__(self, entry_price: float, side: str, multiplier: float = None):
        """Initialize Trailing Stop.
        
        Args:
            entry_price: Entry price of position
            side: BUY or SELL
            multiplier: ATR multiplier (default from config)
        """
        self.entry_price = entry_price
        self.side = side
        self.multiplier = multiplier or config.atr.multiplier
        self.stop_price = entry_price
        self.highest_price = entry_price if side == 'BUY' else entry_price
        self.lowest_price = entry_price if side == 'SELL' else entry_price
        self.is_active = False
        self.trail_distance = 0.0
        self.profit_percent = 0.0
    
    def activate(self, atr_value: float):
        """Activate the trailing stop with ATR value.
        
        Args:
            atr_value: Current ATR value
        """
        if atr_value is None or atr_value <= 0:
            logger.warning('Invalid ATR value for trailing stop activation')
            return
        
        self.trail_distance = atr_value * self.multiplier
        self.is_active = True
        
        if self.side == 'BUY':
            self.stop_price = self.entry_price - self.trail_distance
        else:  # SELL
            self.stop_price = self.entry_price + self.trail_distance
        
        logger.info(f'Trailing Stop activated: Side={self.side}, Stop={self.stop_price:.2f}, Trail Distance={self.trail_distance:.2f}')
    
    def update(self, current_price: float) -> bool:
        """Update trailing stop with current price.
        
        Args:
            current_price: Current market price
        
        Returns:
            True if stop should be triggered
        """
        if not self.is_active:
            return False
        
        if self.side == 'BUY':
            # For long position: trail upward
            if current_price > self.highest_price:
                self.highest_price = current_price
                new_stop = current_price - self.trail_distance
                if new_stop > self.stop_price:
                    self.stop_price = new_stop
                    logger.debug(f'Trailing Stop updated for BUY: New Stop={self.stop_price:.2f}')
            
            # Check if stop triggered
            if current_price <= self.stop_price:
                logger.info(f'Trailing Stop triggered for BUY: Current={current_price:.2f}, Stop={self.stop_price:.2f}')
                return True
            
            self.profit_percent = ((current_price - self.entry_price) / self.entry_price) * 100
        
        else:  # SELL
            # For short position: trail downward
            if current_price < self.lowest_price:
                self.lowest_price = current_price
                new_stop = current_price + self.trail_distance
                if new_stop < self.stop_price:
                    self.stop_price = new_stop
                    logger.debug(f'Trailing Stop updated for SELL: New Stop={self.stop_price:.2f}')
            
            # Check if stop triggered
            if current_price >= self.stop_price:
                logger.info(f'Trailing Stop triggered for SELL: Current={current_price:.2f}, Stop={self.stop_price:.2f}')
                return True
            
            self.profit_percent = ((self.entry_price - current_price) / self.entry_price) * 100
        
        return False
    
    def get_status(self) -> Dict:
        """Get trailing stop status.
        
        Returns:
            Status dictionary
        """
        return {
            'is_active': self.is_active,
            'side': self.side,
            'entry_price': self.entry_price,
            'current_stop': self.stop_price,
            'trail_distance': self.trail_distance,
            'highest_price_seen': self.highest_price if self.side == 'BUY' else None,
            'lowest_price_seen': self.lowest_price if self.side == 'SELL' else None,
            'profit_percent': self.profit_percent
        }
    
    def reset(self):
        """Reset trailing stop."""
        self.is_active = False
        self.stop_price = self.entry_price
        self.trail_distance = 0.0
        self.profit_percent = 0.0
        logger.info('Trailing Stop reset')
