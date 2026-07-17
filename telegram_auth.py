"""Telegram authentication handler for IIFL setup."""
import logging
import os
import re
import time
from typing import Optional
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_AUTH_CODE = 1
CONFIRMING_AUTH = 2


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

    # If it looks like "#authCode=..." (fragment), try to extract via regex
    m = re.search(r'[#?&]?(?:authcode|authCode|auth_code|code)=([^&\s]+)', text)
    if m:
        return m.group(1).strip()

    # Strip leading "authCode=" or similar prefixes
    text = re.sub(r'^(?:authcode|auth_code|code)\s*[:=]\s*', "", text, flags=re.IGNORECASE)

    # Drop anything glued after the code via & or whitespace
    text = text.split("&", 1)[0].split()[0] if text.split() else text

    return text.strip()


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

    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start IIFL authentication flow."""
        logger.info("Starting IIFL authentication flow")

        message = """
🔐 **IIFL Authentication Required**

To establish connection with IIFL server, please provide your AUTH_CODE:

1. Visit: https://api.iiflcapital.com/ or the login URL provided by the bot
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

Could not establish handshake with IIFL server.

Possible reasons:
- Invalid AUTH_CODE
- AUTH_CODE expired (valid for 15 minutes)
- Incorrect credentials
- Server connection issue

Please try again with a fresh AUTH_CODE.
                """
                logger.error("❌ IIFL login failed")

            await query.edit_message_text(message, parse_mode='Markdown')

            return ConversationHandler.END

        except Exception as e:
            logger.error(f"Error during IIFL connection: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ **Error**: {str(e)}\n\nPlease try again.",
                parse_mode='Markdown'
            )
            return WAITING_FOR_AUTH_CODE

    async def retry_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Retry authentication."""
        query = update.callback_query
        await query.answer()

        message = """
🔄 **Retry Authentication**

Please send a new AUTH_CODE or the full redirect URL:
        """

        await query.edit_message_text(message, parse_mode='Markdown')
        return WAITING_FOR_AUTH_CODE

    async def status_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check connection status."""
        try:
            from broker_iifl import broker

            status = broker.get_connection_status()

            message = f"""
📊 **Bot Status**

🟢 Connected: {status.get('connected')}
🏦 Broker: {status.get('broker')}
👤 Username: {status.get('username')}
⏰ Last Update: {status.get('last_update')}
            """

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def setup_handlers(self):
        """Setup Telegram message handlers."""
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("auth", self.start_handler)],
            states={
                WAITING_FOR_AUTH_CODE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.auth_code_handler)
                ],
                CONFIRMING_AUTH: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.auth_code_handler)
                ]
            },
            fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
            allow_reentry=True
        )

        self.app.add_handler(conv_handler)
        self.app.add_handler(CommandHandler("status", self.status_handler))

    async def send_startup_message(self, message: str):
        """Send startup message to Telegram."""
        try:
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    async def start(self):
        """Start Telegram bot."""
        logger.info(f"Starting Telegram bot with token: {self.telegram_token[:20]}...")

        self.app = Application.builder().token(self.telegram_token).build()

        await self.setup_handlers()

        # Send startup message
        startup_msg = """
🤖 **SKY13 Trade Engine Bot Started**

To complete setup and connect to IIFL:
/auth - Start IIFL authentication
/status - Check connection status

Waiting for authentication...
        """

        await self.send_startup_message(startup_msg)

        # Start bot
        await self.app.run_polling()
