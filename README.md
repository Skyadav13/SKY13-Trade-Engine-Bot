# SKY13 Trade Engine (STE) Bot
## Algorithmic Trading Engine for IIFL Capital

An advanced cloud-hosted algorithmic trading engine supporting Paper Trading and Live Trading with TradingView-compatible EMA signals, Telegram integration, automatic recovery, and comprehensive risk management.

## Features

### Trading Modes
- Paper Trading (Default)
- Live Trading (Manual Switch)

### Market Segments
- Cash Market
- Futures
- Options

### Instruments
- NIFTY
- BANKNIFTY
- FINNIFTY
- MIDCPNIFTY
- SENSEX
- Stocks

### Core Components
- **EMA Crossover Strategy** - Fast/Slow EMA with TradingView compatibility
- **RSI Smart Exit** - Trailing stops on overbought/oversold conditions
- **Sideways Market Filter** - Prevents false signals
- **Position Management** - Only one active position at a time
- **Risk Management** - Configurable daily loss limits
- **Recovery System** - Auto-recovery from internet/broker failures
- **Telegram Integration** - Real-time alerts and commands
- **SQLite Database** - Persistent logging and state management

## Installation

```bash
git clone https://github.com/Skyadav13/SKY13-Trade-Engine-Bot.git
cd SKY13-Trade-Engine-Bot
pip install -r requirements.txt
```

## Configuration

1. Copy `.env.example` to `.env`
2. Add your IIFL credentials and Telegram bot token
3. Edit `config.py` for strategy parameters

## Running the Bot

```bash
python main.py
```

## Environment Variables

See `.env.example` for required variables:
- IIFL username/password
- Telegram bot token and chat ID
- Trading parameters

## Development Roadmap

- v0.1 Foundation
- v0.2 Telegram Integration
- v0.3 IIFL Login
- v0.4 Market Data
- v0.5 EMA Engine
- v0.6 Paper Trading
- v0.7 Live Trading
- v0.8 Risk Engine
- v0.9 Recovery Engine
- v1.0 Production Release

## License

MIT
