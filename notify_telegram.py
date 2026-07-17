#!/usr/bin/env python3
"""
Telegram notification script for deployment workflow.
Sends deployment status and instructions to configured Telegram chat.
"""

import os
import sys
import requests

def send_telegram_notification():
    """Send deployment notification to Telegram."""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print('⚠️ Telegram credentials not configured')
        return False
    
    message = """🚀 *SKY13 Trade Engine Bot - Deployment Started*

✅ *Configuration Validated*

📋 *Next Steps to Activate Bot:*

1️⃣ *Get IIFL AUTH_CODE:*
   - Visit: https://markets.iiflcapital.com/
   - Login with your credentials
   - Enter OTP
   - Look at redirect URL for auth_code parameter
   - Copy the AUTH_CODE value

2️⃣ *Send AUTH_CODE to Bot:*
   - Use command: /auth
   - Paste your AUTH_CODE when prompted
   - Confirm to establish connection

3️⃣ *Bot will establish:*
   ✅ IIFL Server connection
   ✅ API handshake
   ✅ Trading readiness confirmation

⏰ *Important:* AUTH_CODE expires in 15 minutes

🔐 Waiting for your AUTH_CODE...
"""
    
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': message
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print('✅ Telegram notification sent successfully')
            return True
        else:
            print(f'⚠️ Telegram notification failed: {response.status_code}')
            print(response.text)
            return False
    except Exception as e:
        print(f'⚠️ Could not send Telegram notification: {e}')
        return False

if __name__ == '__main__':
    success = send_telegram_notification()
    sys.exit(0 if success else 1)
