"""Risk Management for SKY13 Trade Engine."""
import logging
from typing import Dict, Optional
from datetime import datetime, date
from config import config
from database import db

logger = logging.getLogger(__name__)


class RiskManager:
    """Risk Management - Handles loss limits and position sizing."""
    
    def __init__(self):
        """Initialize Risk Manager."""
        self.daily_loss = 0.0
        self.trading_stopped = False
        self.last_reset_date = date.today()
    
    def check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit has been exceeded.
        
        Returns:
            True if within limit, False if exceeded
        """
        # Reset daily loss if new day
        current_date = date.today()
        if current_date != self.last_reset_date:
            self.daily_loss = 0.0
            self.trading_stopped = False
            self.last_reset_date = current_date
            logger.info('Daily loss limit reset')
        
        if config.trading.mode == 'paper':
            return True  # No loss limit in paper mode
        
        limit = config.risk.daily_loss_limit
        if self.daily_loss <= -limit:
            logger.critical(f'Daily loss limit exceeded: {self.daily_loss} <= -{limit}')
            self.trading_stopped = True
            return False
        
        return True
    
    def can_trade(self) -> bool:
        """Check if trading is allowed.
        
        Returns:
            True if trading is allowed
        """
        if self.trading_stopped:
            logger.warning('Trading stopped due to daily loss limit')
            return False
        
        if config.trading.mode == 'paper':
            return True
        
        return self.check_daily_loss_limit()
    
    def update_daily_loss(self, profit_loss: float):
        """Update daily loss with trade result.
        
        Args:
            profit_loss: Profit or loss amount
        """
        self.daily_loss += profit_loss
        logger.info(f'Daily P&L updated: {self.daily_loss}')
    
    def get_position_size(self, account_balance: float, risk_percent: float = 2.0) -> float:
        """Calculate position size based on risk.
        
        Args:
            account_balance: Current account balance
            risk_percent: Risk percentage per trade
        
        Returns:
            Position size
        """
        risk_amount = account_balance * (risk_percent / 100)
        position_size = risk_amount / (config.risk.trailing_stop_percent / 100)
        return position_size
    
    def get_risk_summary(self) -> Dict:
        """Get risk management summary.
        
        Returns:
            Risk summary dictionary
        """
        return {
            'daily_loss': self.daily_loss,
            'daily_limit': config.risk.daily_loss_limit,
            'remaining_loss_buffer': config.risk.daily_loss_limit + self.daily_loss,
            'trading_stopped': self.trading_stopped,
            'mode': config.trading.mode
        }
