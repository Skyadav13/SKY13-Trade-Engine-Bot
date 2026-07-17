"""Configuration Management for SKY13 Trade Engine."""
import os
import secrets
import string
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional

load_dotenv()


def generate_random_key(length: int = 32) -> str:
    """Generate a random key for encryption/session.
    
    Args:
        length: Length of the key to generate (default 32)
    
    Returns:
        Random alphanumeric string
    """
    chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(chars) for _ in range(length))


@dataclass
class BrokerConfig:
    """IIFL Broker Configuration."""
    username: str = os.getenv('IIFL_USERNAME', '')
    password: str = os.getenv('IIFL_PASSWORD', '')
    api_key: str = os.getenv('IIFL_API_KEY', '')
    api_secret: str = os.getenv('IIFL_API_SECRET', '')
    base_url: str = 'https://api.iiflsecurities.com'


@dataclass
class SecurityConfig:
    """Security Configuration for encryption and sessions."""
    encryption_key: str = os.getenv('ENCRYPTION_KEY', '')
    session_secret: str = os.getenv('SESSION_SECRET', '')
    
    def __post_init__(self):
        """Generate keys if not provided."""
        # Generate encryption key if not provided
        if not self.encryption_key:
            self.encryption_key = generate_random_key(32)
        
        # Generate session secret if not provided
        if not self.session_secret:
            self.session_secret = generate_random_key(32)


@dataclass
class TelegramConfig:
    """Telegram Bot Configuration."""
    bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_id: str = os.getenv('TELEGRAM_CHAT_ID', '')
    enabled: bool = os.getenv('TELEGRAM_BOT_TOKEN', '') != ''


@dataclass
class EMAConfig:
    """EMA Strategy Configuration."""
    fast_ema: int = int(os.getenv('FAST_EMA', 9))
    slow_ema: int = int(os.getenv('SLOW_EMA', 21))
    warmup_candles: int = max(int(os.getenv('SLOW_EMA', 21)), 100)  # Minimum 100


@dataclass
class RSIConfig:
    """RSI Configuration."""
    period: int = int(os.getenv('RSI_PERIOD', 14))
    overbought: int = int(os.getenv('RSI_OVERBOUGHT', 70))
    oversold: int = int(os.getenv('RSI_OVERSOLD', 30))


@dataclass
class ATRConfig:
    """ATR Configuration."""
    period: int = int(os.getenv('ATR_PERIOD', 14))
    multiplier: float = 2.0


@dataclass
class ADXConfig:
    """ADX Configuration."""
    period: int = int(os.getenv('ADX_PERIOD', 14))
    trend_threshold: int = 25


@dataclass
class TradingConfig:
    """Trading Configuration."""
    mode: str = os.getenv('TRADING_MODE', 'paper')  # paper or live
    symbol: str = os.getenv('SYMBOL', 'NIFTY')
    timeframe: int = int(os.getenv('TIMEFRAME', 5))  # in minutes
    lot_size: int = int(os.getenv('LOT_SIZE', 1))
    quantity: int = int(os.getenv('QUANTITY', 1))
    instrument: str = 'CASH'  # CASH, FUTURE, OPTION
    expiry: str = os.getenv('OPTIONS_EXPIRY', 'weekly')
    strike_offset: int = int(os.getenv('STRIKE_OFFSET', 0))
    option_type: str = os.getenv('OPTION_TYPE', 'CE')  # CE or PE


@dataclass
class RiskConfig:
    """Risk Management Configuration."""
    daily_loss_limit: float = float(os.getenv('DAILY_LOSS_LIMIT', 3000))
    max_positions: int = 1
    trailing_stop_percent: float = 2.0
    min_ema_separation: float = 5.0  # Minimum % separation between EMAs
    sideways_cooldown: int = 300  # Seconds


@dataclass
class TradingHours:
    """Trading Hours Configuration."""
    start_hour: int = int(os.getenv('START_HOUR', 9))
    start_minute: int = int(os.getenv('START_MINUTE', 15))
    stop_new_entries_hour: int = int(os.getenv('STOP_NEW_ENTRIES_HOUR', 15))
    stop_new_entries_minute: int = int(os.getenv('STOP_NEW_ENTRIES_MINUTE', 15))
    square_off_hour: int = int(os.getenv('SQUARE_OFF_HOUR', 15))
    square_off_minute: int = int(os.getenv('SQUARE_OFF_MINUTE', 30))


@dataclass
class DatabaseConfig:
    """Database Configuration."""
    path: str = os.getenv('DATABASE_PATH', './data/trading.db')
    echo: bool = False  # Set to True for SQL debugging


@dataclass
class LoggingConfig:
    """Logging Configuration."""
    level: str = os.getenv('LOG_LEVEL', 'INFO')
    log_path: str = os.getenv('LOG_PATH', './logs')
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5


class Config:
    """Main Configuration Class."""
    
    def __init__(self):
        self.broker = BrokerConfig()
        self.security = SecurityConfig()
        self.telegram = TelegramConfig()
        self.ema = EMAConfig()
        self.rsi = RSIConfig()
        self.atr = ATRConfig()
        self.adx = ADXConfig()
        self.trading = TradingConfig()
        self.risk = RiskConfig()
        self.trading_hours = TradingHours()
        self.database = DatabaseConfig()
        self.logging = LoggingConfig()
    
    def validate(self) -> bool:
        """Validate configuration."""
        if not self.broker.username or not self.broker.password:
            raise ValueError('IIFL credentials not configured')
        if self.trading.mode not in ['paper', 'live']:
            raise ValueError('Invalid trading mode')
        if self.trading.symbol not in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
            raise ValueError('Invalid symbol')
        return True


# Global config instance
config = Config()
