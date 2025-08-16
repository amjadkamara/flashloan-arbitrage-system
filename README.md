# 🤖 Flashloan Arbitrage Bot

An automated arbitrage trading bot for the Polygon network that uses Aave V3 flashloans to capture price differences between decentralized exchanges.

## 🎯 Features

- **Flashloan Integration**: Uses Aave V3 flashloans for zero-capital arbitrage
- **Multi-DEX Support**: Monitors prices across multiple DEXs (1inch, SushiSwap, QuickSwap, etc.)
- **Real-time Monitoring**: Continuous price scanning and opportunity detection
- **Risk Management**: Built-in safety checks and slippage protection
- **Gas Optimization**: Smart gas price calculation and transaction optimization
- **Multi-channel Alerts**: Discord, Telegram, Slack, and email notifications
- **Comprehensive Logging**: Detailed logging with colored console output
- **Performance Tracking**: Monitor profits, gas costs, and success rates

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Price Feeds   │    │ Opportunity     │    │ Risk Manager    │
│   (1inch API)   │───▶│ Scanner         │───▶│                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
┌─────────────────┐    ┌─────────────────┐            ▼
│  Notifications  │◀───│ Arbitrage Bot   │    ┌─────────────────┐
│  (Multi-channel)│    │ (Orchestrator)  │◀───│ Contract        │
└─────────────────┘    └─────────────────┘    │ Interface       │
                                              └─────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │ FlashloanArb    │
                                              │ Smart Contract  │
                                              └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/flashloan-arbitrage-bot.git
   cd flashloan-arbitrage-bot
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Node.js dependencies**
   ```bash
   npm install
   ```

4. **Setup environment**
   ```bash
   cp config/.env.template .env
   # Edit .env with your configuration
   ```

5. **Deploy smart contract**
   ```bash
   # Deploy to Mumbai testnet
   npm run deploy:testnet
   
   # Deploy to Polygon mainnet
   npm run deploy
   ```

6. **Run the bot**
   ```bash
   python -m bot.arbitrage_bot
   ```

## ⚙️ Configuration

### Environment Variables

Copy `config/.env.template` to `.env` and configure:

```env
# Blockchain
PRIVATE_KEY=your_wallet_private_key
POLYGON_RPC_URL=https://polygon-rpc.com
CONTRACT_ADDRESS=deployed_contract_address

# APIs
ONEINCH_API_KEY=your_1inch_api_key
POLYGONSCAN_API_KEY=your_polygonscan_api_key

# Bot Settings
MIN_PROFIT_PERCENTAGE=1.0
MAX_GAS_PRICE_GWEI=100
SLIPPAGE_TOLERANCE=0.5

# Notifications
DISCORD_WEBHOOK_URL=your_discord_webhook
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Trading Parameters

Key parameters in `config/settings.py`:

- **MIN_PROFIT_PERCENTAGE**: Minimum profit threshold (default: 1.0%)
- **MAX_GAS_PRICE_GWEI**: Maximum gas price limit (default: 100 gwei)
- **MIN_TRADE_AMOUNT**: Minimum trade size (default: 100 MATIC)
- **MAX_TRADE_AMOUNT**: Maximum trade size (default: 10,000 MATIC)
- **SLIPPAGE_TOLERANCE**: Maximum acceptable slippage (default: 0.5%)

## 🎛️ Usage

### Running the Bot

```bash
# Start with default configuration
python -m bot.arbitrage_bot

# Start with custom config
python -m bot.arbitrage_bot --config custom_config.py

# Start in test mode (no real trades)
python -m bot.arbitrage_bot --test-mode

# Start with specific log level
python -m bot.arbitrage_bot --log-level DEBUG
```

### Monitoring

The bot provides several monitoring options:

1. **Console Output**: Real-time colored logging
2. **Log Files**: Detailed logs in `logs/` directory
3. **Notifications**: Alerts via Discord, Telegram, Slack
4. **Performance Script**: `python scripts/monitor_performance.py`

### Testing

```bash
# Run Python tests
python -m pytest tests/

# Run contract tests
npm test

# Run integration tests
python -m pytest tests/test_integration.py

# Test notifications
python -c "from bot.utils.notifications import test_notifications; test_notifications()"
```

## 📊 Trading Strategy

### Arbitrage Logic

1. **Price Discovery**: Continuously monitors token prices across multiple DEXs
2. **Opportunity Detection**: Identifies profitable price differences (> minimum threshold)
3. **Risk Assessment**: Validates trade profitability after gas costs and slippage
4. **Execution**: Executes flashloan arbitrage if profitable
5. **Monitoring**: Tracks transaction status and profits

### Risk Management

- **Slippage Protection**: Maximum acceptable price impact
- **Gas Price Limits**: Prevents execution during high gas periods
- **Position Limits**: Maximum trade size per transaction
- **Profit Thresholds**: Minimum profit requirements
- **Circuit Breakers**: Automatic pause on consecutive failures

## 🏦 Supported DEXs

- **1inch**: Primary aggregator for best prices
- **SushiSwap**: Popular AMM on Polygon
- **QuickSwap**: Native Polygon DEX
- **Uniswap V3**: Cross-chain liquidity
- **Balancer**: Weighted pools
- **Curve**: Stablecoin optimization

## 💰 Economics

### Revenue Sources
- Arbitrage profits from price differences
- MEV capture opportunities

### Costs
- Gas fees for transactions
- 0.09% Aave flashloan fee
- DEX trading fees (typically 0.3%)

### Break-even Analysis
```
Minimum profitable arbitrage = (Gas Cost + Flashloan Fee + Trading Fees) / Trade Size
```

## 📁 Project Structure

```
flashloan_arbitrage_bot/
├── bot/                    # Python bot code
│   ├── arbitrage_bot.py   # Main orchestration
│   ├── opportunity_scanner.py
│   ├── risk_manager.py
│   ├── contract_interface.py
│   ├── price_feeds.py
│   └── utils/             # Utility functions
├── contracts/             # Smart contracts
│   ├── FlashloanArbitrage.sol
│   ├── deploy.js
│   └── interfaces/
├── config/               # Configuration files
│   ├── .env.template
│   ├── settings.py
│   └── addresses.py
├── scripts/              # Utility scripts
├── tests/                # Test files
├── docs/                 # Documentation
└── logs/                 # Log files
```

## 🔧 Development

### Setting up Development Environment

```bash
# Install development dependencies
pip install -r requirements.txt
npm install

# Setup pre-commit hooks
pre-commit install

# Run formatting
black bot/ tests/
prettier --write contracts/

# Run linting
flake8 bot/ tests/
solhint contracts/**/*.sol
```

### Smart Contract Development

```bash
# Compile contracts
npm run compile

# Run contract tests
npm run test

# Deploy to local network
npm run node  # In one terminal
npm run deploy:local  # In another terminal

# Verify contract
npm run verify -- --network polygon <contract_address>
```

## 🚨 Security

### Best Practices

- **Private Keys**: Never commit private keys to version control
- **Environment Variables**: Use `.env` files for sensitive data
- **Contract Auditing**: Test thoroughly before mainnet deployment
- **Error Handling**: Comprehensive error handling and recovery
- **Monitoring**: Real-time monitoring and alerting

### Known Risks

- **Impermanent Loss**: Price movements during execution
- **MEV Competition**: Front-running by other bots
- **Smart Contract Risk**: Bugs in contract code
- **Network Congestion**: High gas prices reducing profitability
- **Market Volatility**: Rapid price changes

## 📚 Documentation

- [Setup Guide](docs/SETUP.md)
- [API Documentation](docs/API.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational purposes only. Trading cryptocurrencies involves substantial risk of loss and is not suitable for every investor. The authors are not responsible for any financial losses incurred through the use of this software. Use at your own risk.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/your-username/flashloan-arbitrage-bot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/flashloan-arbitrage-bot/discussions)
- **Documentation**: [Wiki](https://github.com/your-username/flashloan-arbitrage-bot/wiki)

## 📈 Roadmap

- [ ] Multi-chain support (Ethereum, BSC, Avalanche)
- [ ] Advanced MEV strategies
- [ ] Machine learning price prediction
- [ ] Web dashboard for monitoring
- [ ] Mobile app notifications
- [ ] Liquidity pool arbitrage
- [ ] Cross-chain arbitrage

---

**Made with ❤️ by the Flashloan Arbitrage Bot Team**