#!/usr/bin/env python3
"""
Configuration validation script for deployment workflow.
Validates all required environment variables are set.
"""

import sys
import os
from dotenv import load_dotenv

def validate_config():
    """Validate all required configuration variables."""
    load_dotenv()
    
    print('🔍 Validating Configuration...')
    print()
    
    errors = []
    
    # Required variables
    required_vars = {
        'IIFL_USERNAME': 'IIFL Username',
        'IIFL_PASSWORD': 'IIFL Password',
        'IIFL_VENDOR_KEY': 'IIFL Vendor Key',
        'IIFL_APP_SECRET': 'IIFL App Secret',
        'TELEGRAM_BOT_TOKEN': 'Telegram Bot Token',
        'TELEGRAM_CHAT_ID': 'Telegram Chat ID',
    }
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value or value.strip() == '':
            errors.append(f'{description} not configured')
        else:
            print(f'✅ {description} configured')
    
    # Optional trading config
    trading_vars = {
        'TRADING_MODE': 'Trading Mode',
        'SYMBOL': 'Symbol',
        'TIMEFRAME': 'Timeframe',
        'QUANTITY': 'Quantity',
    }
    
    print()
    print('📊 Trading Configuration:')
    for var, description in trading_vars.items():
        value = os.getenv(var, 'Not set')
        print(f'   {description}: {value}')
    
    if errors:
        print()
        print('❌ Configuration Errors:')
        for error in errors:
            print(f'   - {error}')
        return False
    
    print()
    print('✅ All configuration validated successfully!')
    return True

if __name__ == '__main__':
    success = validate_config()
    sys.exit(0 if success else 1)
