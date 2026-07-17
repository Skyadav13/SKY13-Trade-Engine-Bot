# SKY13 Trade Engine Bot - Setup and Installation Guide

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure IIFL Credentials

**Copy the example configuration:**
```bash
cp .env.example .env
```

**Edit `.env` with your IIFL credentials:**
```bash
# IIFL Broker Credentials
IIFL_USERNAME=your_client_code        # Your IIFL client code
IIFL_PASSWORD=your_password            # Your IIFL password
IIFL_API_KEY=your_api_key              # Optional API key
IIFL_API_SECRET=your_api_secret        # Optional API secret

# Telegram Bot (Optional)
TELEGRAM_BOT_TOKEN=your_bot_token      # Get from @BotFather on Telegram
TELEGRAM_CHAT_ID=your_chat_id          # Your Telegram chat ID

# Trading Settings
TRADING_MODE=paper                     # Start with 'paper' for testing
SYMBOL=NIFTY                           # Trading symbol
TIMEFRAME=5                            # Candle timeframe in minutes
FAST_EMA=9                             # Fast EMA period
SLOW_EMA=21                            # Slow EMA period
DAILY_LOSS_LIMIT=3000                  # Daily loss limit in rupees
QUANTITY=1                             # Lot size to trade
```

### 3. Get IIFL API Credentials

1. **Register on IIFL Developer Portal:**
   - Go to https://developers.iiflcapital.com/
   - Sign up and get API credentials

2. **Generate API Keys:**
   - Log in to your IIFL account
   - Navigate to API settings
   - Generate USER_KEY and ENCRYPTION_KEY

3. **Add to `.env`:**
   ```bash
   IIFL_USERNAME=your_client_code
   IIFL_PASSWORD=your_password
   ```

### 4. Set Up Telegram Alerts (Optional)

1. **Create a Telegram Bot:**
   - Message @BotFather on Telegram
   - Follow the instructions to create a new bot
   - Copy the bot token

2. **Get Your Chat ID:**
   - Start a chat with your new bot
   - Go to: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Find your chat ID from the response

3. **Add to `.env`:**
   ```bash
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

### 5. Run the Bot

**Paper Trading Mode (Recommended for testing):**
```bash
python main.py
```

**Live Trading Mode (When ready):**
```bash
# Change TRADING_MODE=live in .env
python main.py
```

---

## 📋 Configuration Guide

### Trading Symbols

**Supported Indices:**
- NIFTY (default)
- BANKNIFTY
- FINNIFTY
- MIDCPNIFTY
- SENSEX

### Strategy Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| FAST_EMA | 9 | 5-20 | Fast EMA period |
| SLOW_EMA | 21 | 20-50 | Slow EMA period |
| RSI_PERIOD | 14 | 10-20 | RSI calculation period |
| RSI_OVERBOUGHT | 70 | 60-80 | RSI overbought threshold |
| RSI_OVERSOLD | 30 | 20-40 | RSI oversold threshold |
| ATR_PERIOD | 14 | 10-20 | ATR calculation period |
| ADX_PERIOD | 14 | 10-20 | ADX calculation period |

### Risk Management Settings

```
DAILY_LOSS_LIMIT=3000         # Stop trading after losing ₹3000
QUANTITY=1                    # Trade 1 lot per order
TRAILING_STOP_PERCENT=2.0     # Trail stop by 2% of ATR
```

---

## 🔍 Monitoring

### Logs Location

```
./logs/trade_engine.log       # Main trading logs
./data/trading.db             # SQLite database (trades, orders, signals)
```

### View Logs in Real-time

```bash
tail -f logs/trade_engine.log
```

### Database Queries

**View recent trades:**
```bash
sqlite3 data/trading.db "SELECT * FROM trades ORDER BY entry_time DESC LIMIT 10;"
```

**View today's signals:**
```bash
sqlite3 data/trading.db "SELECT * FROM signals WHERE DATE(signal_time) = DATE('now');"
```

---

## 🧪 Testing

### Test Broker Connection

```python
from broker_iifl import broker

# Test login
if broker.login():
    print("✅ Broker connected")
    
    # Test LTP fetch
    ltp = broker.get_ltp('NIFTY')
    print(f"NIFTY LTP: {ltp}")
    
    # Test positions
    positions = broker.get_positions()
    print(f"Open positions: {len(positions)}")
    
    broker.logout()
else:
    print("❌ Connection failed")
```

### Test EMA Strategy

```python
from ema_engine import EMAEngine
from technical_indicators import RSI, ATR, ADX

ema = EMAEngine('NIFTY', fast_period=9, slow_period=21)
rsi = RSI(14)
atr = ATR(14)

# Add sample prices
prices = [17500, 17510, 17505, 17520, 17515, 17525]
for price in prices:
    ema.add_candle(price)
    rsi.add_price(price)
    print(f"Price: {price}, EMA-Fast: {ema.current_ema_fast:.2f}, EMA-Slow: {ema.current_ema_slow:.2f}")
```

---

## 🐛 Troubleshooting

### "IIFLapis SDK not installed"

```bash
pip install IIFLapis
```

### "Login failed" Error

1. **Check credentials:**
   - Verify IIFL_USERNAME and IIFL_PASSWORD in `.env`
   - Ensure account is active
   - Check if API access is enabled

2. **Test credentials manually:**
   ```bash
   python -c "from IIFLapis import IIFLClient; c = IIFLClient(); print(c.client_login('your_code', 'your_pass'))"
   ```

### "No candles returned from broker"

- Market might be closed
- Symbol might be incorrect
- Check IIFL API status

### Database Lock Error

```bash
rm data/trading.db
```

Database will be recreated on next run.

---

## 📊 Performance Optimization

### Market Data Streaming

For real-time market data, implement WebSocket:

```python
# TODO: Implement WebSocket connection for market data
# This will replace the polling-based approach
```

### Backtesting

Use historical candles to test strategy:

```python
from market_data_manager import MarketDataManager

mdm = MarketDataManager('NIFTY', 5)
mdm.load_historical_candles(days_back=30)

# Process candles
for candle in mdm.get_candles():
    # Your strategy logic
    pass
```

---

## 📞 Support

- **IIFL Developer Docs:** https://developers.iiflcapital.com/
- **IIFLapis PyPI:** https://pypi.org/project/IIFLapis/
- **GitHub Repository:** https://github.com/Skyadav13/SKY13-Trade-Engine-Bot

---

## ⚠️ Disclaimer

This trading bot is for educational purposes. Use at your own risk. Always test with paper trading first. The authors are not responsible for any financial losses.

**Risk Management:**
- Start with small quantities
- Use paper trading to test
- Set daily loss limits
- Monitor actively
- Have manual override ready

---

## 🎯 Next Steps

1. ✅ Install dependencies
2. ✅ Configure IIFL credentials
3. ✅ Test broker connection
4. ✅ Run in paper mode
5. ✅ Review logs and trades
6. ✅ Optimize parameters
7. ✅ Enable live trading

**Happy Trading! 📈**
