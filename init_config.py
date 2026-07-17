"""Initialize IIFL API Configuration."""
import os
import logging
from config import config

logger = logging.getLogger(__name__)


def setup_iifl_config():
    """Setup IIFL configuration file required by IIFLapis SDK.
    
    Creates keys.conf file with necessary IIFL SDK configuration.
    """
    try:
        # Create keys.conf content with IIFL SDK requirements
        keys_conf_content = f"""[KEYS]
USERID={config.broker.username}
PASSWORD={config.broker.password}
ENCRYPTION_KEY={config.security.encryption_key}
SESSION_SECRET={config.security.session_secret}
APP_SOURCE=API
USER_KEY={os.getenv('IIFL_USER_KEY', 'DEFAULT_USER_KEY')}
API_KEY={config.broker.api_key}
API_SECRET={config.broker.api_secret}
"""
        
        # Write keys.conf file
        keys_conf_path = 'keys.conf'
        
        with open(keys_conf_path, 'w') as f:
            f.write(keys_conf_content)
        
        logger.info(f'✅ IIFL configuration created at {keys_conf_path}')
        return True
    
    except Exception as e:
        logger.error(f'Failed to setup IIFL configuration: {e}')
        return False


def setup_logging():
    """Setup logging directories if they don't exist."""
    try:
        log_path = config.logging.log_path
        if not os.path.exists(log_path):
            os.makedirs(log_path, exist_ok=True)
            logger.info(f'✅ Created logging directory at {log_path}')
    except Exception as e:
        logger.error(f'Failed to setup logging: {e}')


def setup_database():
    """Setup database directories if they don't exist."""
    try:
        db_path = config.database.path
        db_dir = os.path.dirname(db_path)
        
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f'✅ Created database directory at {db_dir}')
    except Exception as e:
        logger.error(f'Failed to setup database: {e}')


def initialize_all():
    """Initialize all required configurations."""
    logger.info('Initializing SKY13 Trade Engine configurations...')
    
    setup_iifl_config()
    setup_logging()
    setup_database()
    
    logger.info('✅ All configurations initialized successfully')
