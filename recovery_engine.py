"""Recovery Engine for SKY13 Trade Engine - Auto-recovery from failures."""
import logging
from typing import Dict, Optional, List
from datetime import datetime
from database import db
import json

logger = logging.getLogger(__name__)


class RecoveryEngine:
    """Recovery Engine - Handles auto-recovery from internet/broker failures."""
    
    def __init__(self):
        """Initialize Recovery Engine."""
        self.recovery_state = {}
        self.last_recovery_time = None
    
    def save_state(self, state_key: str, state_data: Dict) -> bool:
        """Save state for recovery.
        
        Args:
            state_key: Unique key for state
            state_data: State data to save
        
        Returns:
            True if successful
        """
        try:
            db.log_event('INFO', 'RecoveryEngine', f'Saving recovery state: {state_key}')
            # Save to database for persistence
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO recovery_state (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (state_key, json.dumps(state_data)))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f'Failed to save recovery state: {e}')
            return False
    
    def load_state(self, state_key: str) -> Optional[Dict]:
        """Load saved state for recovery.
        
        Args:
            state_key: State key to load
        
        Returns:
            State data or None
        """
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM recovery_state WHERE key = ?', (state_key,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return json.loads(row[0])
            return None
        except Exception as e:
            logger.error(f'Failed to load recovery state: {e}')
            return None
    
    def check_missing_candles(self, symbol: str, timeframe: int, 
                            last_candle_time: datetime) -> List[Dict]:
        """Check for missing candles after disconnect.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe in minutes
            last_candle_time: Time of last known candle
        
        Returns:
            List of missing candle times
        """
        try:
            from broker_iifl import broker
            
            logger.info(f'Checking for missing candles: {symbol}, since {last_candle_time}')
            
            # Download candles since last known time
            candles = broker.get_candles(symbol, timeframe, days_back=1)
            
            if not candles:
                logger.warning('No candles returned from broker')
                return []
            
            missing_candles = []
            for candle in candles:
                candle_time = datetime.fromisoformat(candle['time']) if isinstance(candle['time'], str) else candle['time']
                if candle_time > last_candle_time:
                    missing_candles.append(candle)
            
            logger.info(f'Found {len(missing_candles)} missing candles')
            return missing_candles
        
        except Exception as e:
            logger.error(f'Error checking missing candles: {e}')
            return []
    
    def sync_positions(self) -> bool:
        """Sync internal positions with broker positions.
        
        Returns:
            True if sync successful
        """
        try:
            from broker_iifl import broker
            
            logger.info('Syncing positions with broker...')
            
            # Get broker positions
            broker_positions = broker.get_positions()
            logger.info(f'Broker has {len(broker_positions)} open positions')
            
            # Compare with database
            # TODO: Implement detailed sync logic
            
            return True
        
        except Exception as e:
            logger.error(f'Error syncing positions: {e}')
            return False
    
    def recover_ema_state(self, ema_engine, symbol: str) -> bool:
        """Recover EMA engine state from saved data.
        
        Args:
            ema_engine: EMA engine instance
            symbol: Trading symbol
        
        Returns:
            True if recovery successful
        """
        try:
            state_key = f'ema_state_{symbol}'
            saved_state = self.load_state(state_key)
            
            if saved_state:
                logger.info(f'Recovering EMA state for {symbol}')
                ema_engine.restore_state(saved_state)
                return True
            else:
                logger.warning(f'No saved EMA state found for {symbol}')
                return False
        
        except Exception as e:
            logger.error(f'Error recovering EMA state: {e}')
            return False
    
    def perform_full_recovery(self, ema_engine, trading_engine, symbol: str) -> bool:
        """Perform full recovery sequence.
        
        Args:
            ema_engine: EMA engine instance
            trading_engine: Trading engine instance
            symbol: Trading symbol
        
        Returns:
            True if recovery successful
        """
        try:
            logger.info(f'Starting full recovery for {symbol}')
            
            # Step 1: Sync positions with broker
            if not self.sync_positions():
                logger.warning('Position sync failed, continuing with recovery')
            
            # Step 2: Recover EMA state
            if not self.recover_ema_state(ema_engine, symbol):
                logger.warning('EMA state recovery failed, will recalculate')
            
            # Step 3: Check for missing candles and update EMA
            last_ema_state = self.load_state(f'ema_state_{symbol}')
            if last_ema_state:
                last_time = datetime.fromisoformat(last_ema_state.get('timestamp', datetime.now().isoformat()))
                missing_candles = self.check_missing_candles(symbol, 5, last_time)  # TODO: use configured timeframe
                
                for candle in missing_candles:
                    ema_engine.add_candle(candle['close'], candle.get('volume', 0))
                    logger.info(f'Updated EMA with missing candle: {candle}')
            
            # Step 4: Verify broker positions
            broker_positions = self._get_broker_positions()
            logger.info(f'Broker positions after recovery: {len(broker_positions)}')
            
            self.last_recovery_time = datetime.now()
            logger.info(f'✅ Full recovery completed at {self.last_recovery_time}')
            
            db.log_event('INFO', 'RecoveryEngine', 'Full recovery completed successfully')
            return True
        
        except Exception as e:
            logger.error(f'Error during full recovery: {e}')
            db.log_event('ERROR', 'RecoveryEngine', f'Recovery failed: {e}')
            return False
    
    def _get_broker_positions(self) -> List[Dict]:
        """Get positions from broker (helper).
        
        Returns:
            List of positions
        """
        try:
            from broker_iifl import broker
            return broker.get_positions()
        except Exception as e:
            logger.error(f'Error getting broker positions: {e}')
            return []
    
    def get_recovery_status(self) -> Dict:
        """Get recovery status information.
        
        Returns:
            Recovery status dictionary
        """
        return {
            'last_recovery_time': self.last_recovery_time.isoformat() if self.last_recovery_time else None,
            'recovery_enabled': True,
            'state_keys': list(self.recovery_state.keys())
        }
