"""Telegram authentication handler for IIFL setup.

Provides robust IIFL appkey detection and a /debug_env command to inspect
what the bot sees (masked). Accepts raw authCode or full redirect URLs.
Includes a background getUpdates poller to pick up pasted auth codes.
"""
import logging
import os
import re
import time
import threading
from typing import Optional
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from dotenv import load_dotenv
import requests

# Load .env if present so keys set in .env are visible at runtime
load_dotenv()

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_AUTH_CODE = 1
CONFIRMING_AUTH = 2

# Module-level cursor for Telegram getUpdates polling (shared with background poller)
_telegram_update_offset = 0


def _mask_key(key: str) -> str:
    if not key:
        return '<missing>'
    if len(key) <= 8:
        return key[:2] + '...' + key[-2:]
    return key[:4] + '...' + key[-4:]


def _get_iifl_appkey() -> Optional[str]:
    """Locate the IIFL appkey from several possible sources.

    Order of checks:
      1. config.broker.api_key or config.broker.vendor_key (if config importable)
      2. Environment variables (IIFL_API_KEY, IIFL_VENDOR_KEY, IIFL_CLIENT_KEY, IIFL_CLIENT_CODE)
      3. Parse a local .env file (if present) as a fallback

    Returns the raw key string or None.
    """
    # 1) Try config if available
    try:
        from config import config
        k = getattr(config.broker, 'api_key', '') or getattr(config.broker, 'vendor_key', '')
        if k:
            return k
    except Exception:
        pass

    # 2) Common environment variable names
    for name in ('IIFL_API_KEY', 'IIFL_VENDOR_KEY', 'IIFL_CLIENT_KEY', 'IIFL_CLIENT_CODE'):
        v = os.getenv(name)
        if v and v.strip():
            return v.strip()

    # 3) As a last resort, parse a .env file in repo root (if present)
    dotenv_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(dotenv_path):
        try:
            with open(dotenv_path, 'r') as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' not in line:
                        continue
                    name, val = line.split('=', 1)
                    name = name.strip()
                    val = val.strip().strip('"').strip("'")
                    if name in ('IIFL_API_KEY', 'IIFL_VENDOR_KEY', 'IIFL_CLIENT_KEY', 'IIFL_CLIENT_CODE') and val:
                        return val
        except Exception:
            pass

    return None


def extract_auth_code(raw: str) -> str:
    """Normalize user input into a bare auth code.

    Accepts:
      - bare code
      - full redirect URL containing ?authCode=...
      - query tail like "authCode=...&clientid=..."
      - code glued to trailing params

    Returns empty string on failure.
    """
    text = (raw or "").strip()
    if not text:
        return ""

    # Full URL: parse the query string properly (handles ?authCode=...)
    if '://' in text:
        try:
            qs = parse_qs(urlparse(text).query)
            for key in ('authCode', 'authcode', 'code', 'auth_code'):
                if qs.get(key):
                    return qs[key][0].strip()
        except Exception:
            pass

    # If it looks like a query/fragment containing authCode etc.
    m = re.search(r'[#?&]?(?:authcode|authCode|auth_code|code)=([^&\s]+)', text)
    if m:
        return m.group(1).strip()

    # Strip leading "authCode=" or similar prefixes
    text = re.sub(r'^(?:authcode|auth_code|code)\s*[:=]\s*', '', text, flags=re.IGNORECASE)

    # Drop anything glued after the code via & or whitespace
    text = text.split('&', 1)[0].split()[0] if text.split() else text

    return text.strip()


def poll_telegram_authcode(timeout_s: int = 8, not_before_ts: float = 0.0) -> str:
    """Long-poll Telegram getUpdates for a new text message from the configured
    TELEGRAM_CHAT_ID and treat its (trimmed) text as a candidate authCode.
    Returns "" if none. Advances the offset so the same message is never consumed twice.
    """
    global _telegram_update_offset
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = str(os.getenv('TELEGRAM_CHAT_ID', ''))
    if not token or not chat_id:
        return ""

    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={
                'offset': _telegram_update_offset,
                'timeout': timeout_s,
                'allowed_updates': '["message"]',
            },
            timeout=timeout_s + 5,
        )
        data = resp.json()
        if not data.get('ok'):
            return ""
        for update in data.get('result', []):
            _telegram_update_offset = update['update_id'] + 1
            msg = update.get('message', {})
            msg_chat_id = str(msg.get('chat', {}).get('id', ''))
            text = (msg.get('text') or '').strip()
            msg_ts = msg.get('date', 0)
            if msg_chat_id != chat_id or not text:
                continue
            if not_before_ts and msg_ts < not_before_ts:
                # Acknowledge old message but don't treat as code
                logger.warning('Ignoring stale queued Telegram message (older than not_before_ts)')
                continue
            # Accept prefixed messages like "authCode: XXX" or "/authcode XXX"
            for prefix in ('authcode:', 'authcode', '/authcode'):
                if text.lower().startswith(prefix):
                    text = text[len(prefix):].strip(' :')
                    break
            if text:
                return text
    except Exception as exc:
        logger.warning('Telegram getUpdates poll failed: %s', exc)
    return ''


class IIFLAuthHandler:
    """Handle IIFL authentication via Telegram."""

    def __init__(self, telegram_token: str, chat_id: str):
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.auth_code: Optional[str] = None
        self.app: Optional[Application] = None
        self._poller_thread: Optional[threading.Thread] = None
        self._stop_poller = threading.Event()

    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start IIFL authentication flow and show the exact login URL."""
        logger.info('Starting IIFL authentication flow')

        iifl_key = _get_iifl_appkey()
        if iifl_key:
            login_url = f'https://markets.iiflcapital.com/?appkey={iifl_key}&v=1'
            logger.info('IIFL appkey detected: %s', _mask_key(iifl_key))
        else:
            login_url = 'https://markets.iiflcapital.com/?appkey=<MISSING_IIFL_API_KEY>&v=1'
            logger.warning('IIFL appkey not found in environment/config/.env')

        message = f"""
🔐 **IIFL Authentication Required**

To establish connection with IIFL server, please provide your AUTH_CODE:

1. Visit: {login_url}
2. Login with your credentials
3. Enter OTP
4. Copy AUTH_CODE from redirect URL (or paste the full redirect URL) and send it here

⏰ AUTH_CODE expires in 15 minutes
"""

        await update.message.reply_text(message, parse_mode='Markdown')
        return WAITING_FOR_AUTH_CODE

    async def auth_code_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        raw = (update.message.text or '').strip()
        code = extract_auth_code(raw)
        if not code or len(code) < 5:
            await update.message.reply_text('❌ Invalid AUTH_CODE format. Please try again or paste the full redirect URL.')
            return WAITING_FOR_AUTH_CODE

        self.auth_code = code
        logger.info('Received AUTH_CODE input (len=%d).', len(code))
        try:
            with open('.auth_received', 'a') as f:
                f.write(f"{datetime.now().isoformat()} - received auth input (len={len(code)})\n")
        except Exception:
            pass

        keyboard = [
            [InlineKeyboardButton('✅ Confirm', callback_data='confirm_auth'), InlineKeyboardButton('❌ Retry', callback_data='retry_auth')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(f"🔑 AUTH_CODE received: `{code[:12]}...`\n\nConfirm to proceed with IIFL handshake?", parse_mode='Markdown', reply_markup=reply_markup)
        return CONFIRMING_AUTH

    async def confirm_auth_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text('🔄 Testing IIFL connection...', parse_mode='Markdown')
            from config import config
            from broker_iifl import broker
            import os

            os.environ['IIFL_AUTH_CODE'] = self.auth_code
            logger.info('Attempting IIFL broker login...')
            login_result = broker.login()

            if login_result:
                message = """
✅ **IIFL Handshake Successful!**

🤝 Connected to IIFL Server
📊 Broker: IIFL Securities
🟢 Status: Online
⏰ Connection Time: %s

**Bot is ready to start trading!**

📈 Configuration:
- Trading Mode: %s
- Symbol: %s
- Timeframe: %s min

Use /status to check connection status
""" % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), config.trading.mode, config.trading.symbol, config.trading.timeframe)

                logger.info('✅ IIFL login successful')
                
                  try:
                with open('.iifl_auth', 'w') as f:
                    f.write(self.auth_code)
                logger.info('AUTH_CODE saved to .iifl_auth')
            except Exception as e:
                logger.warning('Could not write .iifl_auth: %s', e)
            else:
                message = "Authentication failed or token invalid."
                logger.error(message)
                return False
            return True

        
                
                
                
                
                
                
                #try:
                    #with open('.iifl_auth', 'w') as f:
                      #  f.write(self.auth_code)
                   # logger.info('AUTH_CODE saved to .iifl_auth')
               # except Exception as e:
                  #  logger.warning('Could not write .iifl_auth: %s', e)
           # else:
              #  message = ""
 #We attempted many commits and some previous create_or_update_file calls injected commit text into the file earlier. Need to replace rest of file with correct code. Let's finish file properly.
