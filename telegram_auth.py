"""Telegram authentication handler for IIFL setup."""
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

import requests

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_AUTH_CODE = 1
CONFIRMING_AUTH = 2

# Module-level cursor for Telegram getUpdates polling (shared with background poller)
_telegram_update_offset = 0


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
    if "://" in text:
        try:
            qs = parse_qs(urlparse(text).query)
            for key in ("authCode", "authcode", "code", "auth_code"):
                if qs.get(key):
                    return qs[key][0].strip()
        except Exception:
            pass

    # If it looks like a query/fragment containing authCode etc.
    m = re.search(r'[#?&]?(?:authcode|authCode|auth_code|code)=([^&\s]+)', text)
    if m:
        return m.group(1).strip()

    # Strip leading "authCode=" or similar prefixes
    text = re.sub(r'^(?:authcode|auth_code|code)\s*[:=]\s*', "", text, flags=re.IGNORECASE)

    # Drop anything glued after the code via & or whitespace
    text = text.split("&", 1)[0].split()[0] if text.split() else text

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
                "offset": _telegram_update_offset,
                "timeout": timeout_s,
                "allowed_updates": '["message"]',
            },
            timeout=timeout_s + 5,
        )
        data = resp.json()
        if not data.get("ok"):
            return ""
        for update in data.get("result", []):
            _telegram_update_offset = update["update_id"] + 1
            msg = update.get("message", {})
            msg_chat_id = str(msg.get("chat", {}).get("id", ""))
            text = (msg.get("text") or "").strip()
            msg_ts = msg.get("date", 0)
            if msg_chat_id != chat_id or not text:
                continue
            if not_before_ts and msg_ts < not_before_ts:
                # Acknowledge old message but don't treat as code
                logger.warning("Ignoring stale queued Telegram message (older than not_before_ts)")
                continue
            # Accept prefixed messages like "authCode: XXX" or "/authcode XXX"
            for prefix in ("authcode:", "authcode", "/authcode"):
                if text.lower().startswith(prefix):
                    text = text[len(prefix):].strip(" :")
                    break
            if text:
                return text
    except Exception as exc:
        logger.warning("Telegram getUpdates poll failed: %s", exc)
    return ""


class IIFLAuthHandler:
    """Handle IIFL authentication via Telegram.

    This class accepts either a raw auth_code or a full redirect URL pasted
    into the Telegram chat. When a code is received it confirms with the
    user and then attempts the broker handshake (broker.login()). On success
    it persists the code to .iifl_auth for session persistence.
    """

    def __init__(self, telegram_token: str, chat_id: str):
        """Initialize auth handler.

        Args:
            telegram_token: Telegram bot token
            chat_id: Target chat ID for notifications
        """
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.auth_code: Optional[str] = None
        self.app: Optional[Application] = None
        self._poller_thread: Optional[threading.Thread] = None
        self._stop_poller = threading.Event()

    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start IIFL authentication flow."""
        logger.info("Starting IIFL authentication flow")

        # Build login URL from config or environment
        try:
            from config import config
            iifl_key = config.broker.api_key or config.broker.vendor_key
        except Exception:
            iifl_key = os.getenv('IIFL_API_KEY') or os.getenv('IIFL_VENDOR_KEY') or ''

        if iifl_key:
            login_url = f'https://markets.iiflcapital.com/?appkey={iifl_key}&v=1'
        else:
            login_url = 'https://markets.iiflcapital.com/?appkey=<YOUR_IIFL_API_KEY>&v=1'

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
        """Handle AUTH_CODE submission (raw code or full URL)."""
        raw = (update.message.text or "").strip()
        code = extract_auth_code(raw)

        if not code or len(code) < 5:
            await update.message.reply_text("❌ Invalid AUTH_CODE format. Please try again or paste the full redirect URL.")
            return WAITING_FOR_AUTH_CODE

        self.auth_code = code
        logger.info(f"Received AUTH_CODE input (len={len(code)}). Showing confirmation to user.")

        # write a short marker for debugging / CI tracing (no secret in logs)
        try:
            with open('.auth_received', 'a') as f:
                f.write(f"{datetime.now().isoformat()} - received auth input (len={len(code)})\n")
        except Exception:
            pass

        # Confirm receipt
        keyboard = [
            [InlineKeyboardButton("✅ Confirm", callback_data='confirm_auth'),
             InlineKeyboardButton("❌ Retry", callback_data='retry_auth')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🔑 AUTH_CODE received: `{code[:12]}...`\n\nConfirm to proceed with IIFL handshake?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

        return CONFIRMING_AUTH

    async def confirm_auth_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm and test IIFL connection."""
        query = update.callback_query
        await query.answer()

        try:
            await query.edit_message_text("🔄 Testing IIFL connection...", parse_mode='Markdown')

            # Import here to use the auth_code and broker
            from config import config
            from broker_iifl import broker
            import os

            # Set auth code in environment for init_config / IIFL client
            os.environ['IIFL_AUTH_CODE'] = self.auth_code

            # Attempt login
            logger.info("Attempting IIFL broker login...")
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
                """ % (
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    config.trading.mode,
                    config.trading.symbol,
                    config.trading.timeframe
                )

                logger.info("✅ IIFL login successful")

                # persist the code for session-persistence
                try:
                    with open('.iifl_auth', 'w') as f:
                        f.write(self.auth_code)
                    logger.info('AUTH_CODE saved to .iifl_auth')
                except Exception as e:
                    logger.warning(f'Could not write .iifl_auth: {e}')

            else:
                message = """
❌ **IIFL Connection Failed**

I will now call to create commit with updated file.  (This is the content to commit.)