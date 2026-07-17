"""Market Data Manager - Handles real-time market data and candle management."""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque
from database import db
from config import config

logger = logging.getLogger(__name__)


class Candle:
    """OHLCV Candle data structure."""
    
    def __init__(self, timestamp: datetime, open_price: float, high: float, 
                 low: float, close: float, volume: int):
        """Initialize Candle.
        
        Args:
            timestamp: Candle timestamp
            open_price: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume
        """
        self.timestamp = timestamp
        self.open = open_price
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }


class MarketDataManager:
    """Manages market data and candle aggregation."""
    
    def __init__(self, symbol: str, timeframe: int):
        """Initialize Market Data Manager.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe in minutes
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.candles = deque(maxlen=500)  # Keep last 500 candles
        self.current_candle = None
        self.last_tick_time = None
        self.ticks = []
    
    def add_tick(self, price: float, volume: int = 0, timestamp: datetime = None) -> Optional[Candle]:
        """Add a market tick.
        
        Args:
            price: Tick price
            volume: Tick volume
            timestamp: Tick timestamp (default: now)
        
        Returns:
            Completed candle if candle closed, else None
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self.last_tick_time = timestamp
        
        # Determine candle time
        candle_time = self._get_candle_time(timestamp)
        
        # Initialize or update current candle
        if self.current_candle is None:
            self.current_candle = {
                'time': candle_time,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume
            }
            self.ticks = []
        else:
            # Check if new candle
            if candle_time > self.current_candle['time']:
                # Close current candle
                completed_candle = self.current_candle
                
                # Start new candle
                self.current_candle = {
                    'time': candle_time,
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': volume
                }
                
                self.candles.append(completed_candle)
                self.ticks = []
                
                logger.debug(f'Candle closed: {completed_candle["time"]} OHLC={completed_candle["open"]:.2f}/{completed_candle["high"]:.2f}/{completed_candle["low"]:.2f}/{completed_candle["close"]:.2f}')
                
                # Save to database
                self._save_candle(completed_candle)
                
                return Candle(
                    timestamp=datetime.fromisoformat(completed_candle['time']),
                    open_price=completed_candle['open'],
                    high=completed_candle['high'],
                    low=completed_candle['low'],
                    close=completed_candle['close'],
                    volume=completed_candle['volume']
                )
            else:
                # Update current candle
                self.current_candle['high'] = max(self.current_candle['high'], price)
                self.current_candle['low'] = min(self.current_candle['low'], price)
                self.current_candle['close'] = price
                self.current_candle['volume'] += volume
        
        self.ticks.append({'price': price, 'volume': volume, 'time': timestamp})
        return None
    
    def get_last_candle(self) -> Optional[Dict]:
        """Get the last completed candle.
        
        Returns:
            Last candle dictionary or None
        """
        if len(self.candles) > 0:
            return self.candles[-1]
        return None
    
    def get_candles(self, count: int = 50) -> List[Dict]:
        """Get last N candles.
        
        Args:
            count: Number of candles
        
        Returns:
            List of candles
        """
        return list(self.candles)[-count:]
    
    def get_current_candle(self) -> Optional[Dict]:
        """Get current incomplete candle.
        
        Returns:
            Current candle or None
        """
        return self.current_candle
    
    def load_historical_candles(self, days_back: int = 30) -> bool:
        """Load historical candles from broker.
        
        Args:
            days_back: Number of days to load
        
        Returns:
            True if successful
        """
        try:
            from broker_iifl import broker
            
            logger.info(f'Loading {days_back} days of historical candles for {self.symbol}')
            candles = broker.get_candles(self.symbol, self.timeframe, days_back)
            
            if candles:
                for candle in candles:
                    self.candles.append(candle)
                logger.info(f'Loaded {len(candles)} candles')
                return True
            else:
                logger.warning('No candles returned from broker')
                return False
        
        except Exception as e:
            logger.error(f'Error loading historical candles: {e}')
            return False
    
    def _get_candle_time(self, timestamp: datetime) -> str:
        """Calculate candle open time for a given timestamp.
        
        Args:
            timestamp: Timestamp
        
        Returns:
            Candle time string (ISO format)
        """
        # Round down to nearest candle time
        minutes = timestamp.minute - (timestamp.minute % self.timeframe)
        candle_time = timestamp.replace(minute=minutes, second=0, microsecond=0)
        return candle_time.isoformat()
    
    def _save_candle(self, candle: Dict) -> bool:
        """Save candle to database.
        
        Args:
            candle: Candle dictionary
        
        Returns:
            True if successful
        """
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO candles 
                (symbol, timeframe, open_time, close_time, open_price, high_price, low_price, close_price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.symbol,
                self.timeframe,
                candle['time'],
                candle['time'],
                candle['open'],
                candle['high'],
                candle['low'],
                candle['close'],
                candle['volume']
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f'Error saving candle: {e}')
            return False
    
    def get_market_stats(self) -> Dict:
        """Get market statistics.
        
        Returns:
            Market stats dictionary
        """
        if len(self.candles) == 0:
            return {}
        
        closes = [c['close'] for c in self.candles]
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'candles_count': len(self.candles),
            'current_price': closes[-1] if closes else None,
            'day_high': max(closes),
            'day_low': min(closes),
            'day_change': ((closes[-1] - closes[0]) / closes[0] * 100) if closes and closes[0] != 0 else 0
        }
