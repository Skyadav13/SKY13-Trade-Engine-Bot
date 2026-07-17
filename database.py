"""Database models and management for SKY13 Trade Engine."""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import json
from config import config
import os


class Database:
    """SQLite Database Manager."""
    
    def __init__(self):
        """Initialize database connection."""
        self.db_path = config.database.path
        os.makedirs(os.path.dirname(self.db_path) or '.', exist_ok=True)
        self.init_tables()
    
    def get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_tables(self):
        """Initialize database tables."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,  -- BUY or SELL
                instrument TEXT NOT NULL,  -- CASH, FUTURE, OPTION
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT DEFAULT 'OPEN',  -- OPEN, CLOSED, CANCELLED
                entry_time TIMESTAMP NOT NULL,
                exit_time TIMESTAMP,
                profit_loss REAL,
                ema_fast REAL,
                ema_slow REAL,
                rsi_value REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE,
                trade_id TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT DEFAULT 'PENDING',  -- PENDING, FILLED, REJECTED, CANCELLED
                order_time TIMESTAMP NOT NULL,
                fill_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
            )
        ''')
        
        # EMA values table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ema_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                ema_fast REAL NOT NULL,
                ema_slow REAL NOT NULL,
                price REAL NOT NULL,
                volume INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Market data candles
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe INTEGER NOT NULL,
                open_time TIMESTAMP NOT NULL,
                close_time TIMESTAMP NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                close_price REAL NOT NULL,
                volume INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, open_time)
            )
        ''')
        
        # Signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,  -- BUY, SELL
                signal_time TIMESTAMP NOT NULL,
                ema_fast REAL NOT NULL,
                ema_slow REAL NOT NULL,
                price REAL NOT NULL,
                strength REAL,  -- 0-1 signal strength
                filters_passed TEXT,  -- JSON of filter results
                executed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,  -- INFO, WARNING, ERROR, CRITICAL
                module TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                data TEXT,  -- JSON additional data
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Configuration table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configuration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Recovery state table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recovery_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def insert_trade(self, trade_data: Dict) -> str:
        """Insert a new trade."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (trade_id, symbol, side, instrument, price, quantity, 
                              entry_time, ema_fast, ema_slow, rsi_value, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data['trade_id'],
            trade_data['symbol'],
            trade_data['side'],
            trade_data['instrument'],
            trade_data['price'],
            trade_data['quantity'],
            trade_data['entry_time'],
            trade_data.get('ema_fast'),
            trade_data.get('ema_slow'),
            trade_data.get('rsi_value'),
            'OPEN'
        ))
        conn.commit()
        conn.close()
        return trade_data['trade_id']
    
    def insert_order(self, order_data: Dict) -> str:
        """Insert a new order."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (order_id, trade_id, symbol, side, price, quantity, 
                              order_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_data['order_id'],
            order_data.get('trade_id'),
            order_data['symbol'],
            order_data['side'],
            order_data['price'],
            order_data['quantity'],
            order_data['order_time'],
            'PENDING'
        ))
        conn.commit()
        conn.close()
        return order_data['order_id']
    
    def insert_ema_values(self, ema_data: Dict):
        """Insert EMA values."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ema_values (symbol, timeframe, timestamp, ema_fast, ema_slow, price, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            ema_data['symbol'],
            ema_data['timeframe'],
            ema_data['timestamp'],
            ema_data['ema_fast'],
            ema_data['ema_slow'],
            ema_data['price'],
            ema_data.get('volume')
        ))
        conn.commit()
        conn.close()
    
    def insert_signal(self, signal_data: Dict):
        """Insert a signal."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO signals (symbol, signal_type, signal_time, ema_fast, ema_slow, price, strength, filters_passed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            signal_data['symbol'],
            signal_data['signal_type'],
            signal_data['signal_time'],
            signal_data['ema_fast'],
            signal_data['ema_slow'],
            signal_data['price'],
            signal_data.get('strength'),
            json.dumps(signal_data.get('filters_passed', {}))
        ))
        conn.commit()
        conn.close()
    
    def log_event(self, level: str, module: str, message: str, data: Optional[Dict] = None):
        """Log an event."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO logs (level, module, message, timestamp, data)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            level,
            module,
            message,
            datetime.now(),
            json.dumps(data) if data else None
        ))
        conn.commit()
        conn.close()
    
    def get_open_positions(self, symbol: str) -> List[Dict]:
        """Get open positions for a symbol."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM trades WHERE symbol = ? AND status = 'OPEN' ORDER BY entry_time DESC
        ''', (symbol,))
        positions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return positions
    
    def update_trade_status(self, trade_id: str, status: str, exit_time: datetime = None, pl: float = None):
        """Update trade status."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE trades SET status = ?, exit_time = ?, profit_loss = ? WHERE trade_id = ?
        ''', (status, exit_time, pl, trade_id))
        conn.commit()
        conn.close()


# Global database instance
db = Database()
