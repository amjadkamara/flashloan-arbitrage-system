# Complete setup guide 
# docs/SETUP.md

# 🚀 Flashloan Arbitrage Bot - Complete Setup Guide

Welcome to the comprehensive setup guide for the Flashloan Arbitrage Bot. This guide will walk you through every step needed to get your arbitrage bot up and running on Polygon.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Configuration](#configuration)
- [Smart Contract Deployment](#smart-contract-deployment)
- [Testing](#testing)
- [Running the Bot](#running-the-bot)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## 🔧 Prerequisites

### System Requirements
- **Python**: 3.8 or higher
- **Node.js**: 16 or higher
- **npm**: 8 or higher
- **Git**: Latest version
- **Operating System**: Windows 10+, macOS 10.15+, or Linux

### Required Accounts & API Keys
1. **Polygon RPC Provider**
   - Alchemy (recommended): https://www.alchemy.com/
   - Infura: https://infura.io/
   - QuickNode: https://www.quicknode.com/

2. **Price Feed APIs**
   - CoinGecko API: https://www.coingecko.com/en/api
   - 1inch API: https://docs.1inch.io/docs/aggregation-protocol/api/swagger
   - DEX APIs (Uniswap, SushiSwap, etc.)

3. **Wallet**
   - MetaMask or similar wallet with Polygon network added
   - Some MATIC for gas fees (minimum 10 MATIC recommended)

### Knowledge Requirements
- Basic understanding of:
  - Command line/terminal usage
  - Cryptocurrency trading
  - Smart contracts and DeFi
  - Python programming (helpful but not required)

## ⚡ Quick Start

For experienced developers who want to get started immediately:

```bash
# 1. Clone and setup
git clone <your-repo>
cd flashloan_arbitrage_bot
python scripts/setup_environment.py

# 2. Configure
cp config/.env.template config/.env
# Edit config/.env with your API keys

# 3. Deploy and run
python scripts/deploy_contract.py
python bot/arbitrage_bot.py
```

## 🔨 Detailed Setup

### Step 1: Environment Setup

#### 1.1 Clone the Repository
```bash
git clone <your-repository-url>
cd flashloan_arbitrage_bot
```

#### 1.2 Automated Setup
Run the automated setup script:
```bash
python scripts/setup_environment.py
```

This will:
- ✅ Check system prerequisites
- ✅ Create Python virtual environment
- ✅ Install all dependencies
- ✅ Create directory structure
- ✅ Generate activation scripts
- ✅ Compile smart contracts

#### 1.3 Manual Setup (if automated fails)

**Create Virtual Environment:**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

**Install Python Dependencies:**
```bash
pip install -r requirements.txt
```

**Install Node.js Dependencies:**
```bash
npm install
```

### Step 2: Configuration

#### 2.1 Environment Variables
Create your environment file:
```bash
cp config/.env.template config/.env
```

Edit `config/.env` with your settings:
```env
# Blockchain Configuration
NETWORK=polygon
WEB3_PROVIDER_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
PRIVATE_KEY=your_wallet_private_key_here

# Trading Configuration
MIN_PROFIT_THRESHOLD=5.0
MAX_TRADE_SIZE=1000.0
GAS_PRICE_LIMIT=100
SLIPPAGE_TOLERANCE=0.5

# API Keys
COINGECKO_API_KEY=your_coingecko_key
ONEINCH_API_KEY=your_1inch_key
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id

# Safety Settings
ENABLE_TESTNET=false
DRY_RUN_MODE=true
MAX_FAILED_TRADES=3
ENABLE_NOTIFICATIONS=true
```

#### 2.2 Security Best Practices

**Private Key Security:**
- Never commit your `.env` file to version control
- Use a dedicated wallet for trading (not your main wallet)
- Start with small amounts for testing
- Consider using hardware wallets for large amounts

**Environment Separation:**
- Use testnet first (Mumbai testnet for Polygon)
- Enable dry run mode initially
- Gradually increase trade sizes

### Step 3: Smart Contract Deployment

#### 3.1 Compile Contracts
```bash
npx hardhat compile
```

#### 3.2 Deploy to Testnet (Recommended First)
```bash
# Switch to testnet in config/.env
NETWORK=mumbai
ENABLE_TESTNET=true

# Deploy
python scripts/deploy_contract.py --network mumbai
```

#### 3.3 Deploy to Mainnet
```bash
# Switch to mainnet in config/.env
NETWORK=polygon
ENABLE_TESTNET=false

# Deploy (only after thorough testing!)
python scripts/deploy_contract.py --network polygon
```

The deployment script will:
- ✅ Deploy the FlashloanArbitrage contract
- ✅ Verify the contract on PolygonScan
- ✅ Save the contract address to `config/addresses.py`
- ✅ Test basic contract functions

### Step 4: Testing

#### 4.1 Run Unit Tests
```bash
python -m pytest tests/test_contract.py -v
python -m pytest tests/test_bot.py -v
```

#### 4.2 Integration Tests
```bash
python -m pytest tests/test_integration.py -v
```

#### 4.3 Testnet Testing
```bash
# Ensure testnet configuration
ENABLE_TESTNET=true
DRY_RUN_MODE=false

# Run bot in testnet mode
python bot/arbitrage_bot.py --testnet
```

### Step 5: Production Deployment

#### 5.1 Final Configuration Check
Before going live, verify:
- [ ] All API keys are working
- [ ] Contract deployed successfully
- [ ] Testnet testing completed
- [ ] Wallet has sufficient MATIC for gas
- [ ] Monitoring systems ready
- [ ] Emergency stop procedures understood

#### 5.2 Start the Bot
```bash
# Activate environment
# Windows: activate.bat
# macOS/Linux: source activate.sh

# Start monitoring (separate terminal)
python scripts/monitor_performance.py

# Start the bot
python bot/arbitrage_bot.py
```

## 📊 Monitoring & Management

### Real-time Monitoring
```bash
python scripts/monitor_performance.py
```

The monitor displays:
- 📈 Trading performance metrics
- 🎯 Opportunity analysis
- 📊 Recent trade history
- 🖥️ System resource usage
- 🚨 Active alerts

### Log Analysis
Logs are saved to `logs/arbitrage_bot.log`:
```bash
# View recent logs
tail -f logs/arbitrage_bot.log

# Search for specific events
grep "profit" logs/arbitrage_bot.log
```

### Performance Reports
Session reports are automatically generated in `data/`:
- Daily metrics: `metrics_YYYYMMDD.json`
- Session reports: `session_report_YYYYMMDD_HHMMSS.txt`

## 🔒 Security & Risk Management

### Built-in Safety Features
- **Dry Run Mode**: Test without actual trades
- **Maximum Trade Size**: Limits exposure
- **Failed Trade Limits**: Auto-stop on consecutive failures
- **Gas Price Limits**: Prevents expensive transactions
- **Slippage Protection**: Limits price impact
- **Emergency Stop**: Manual override capability

### Recommended Practices
1. **Start Small**: Begin with minimal trade sizes
2. **Monitor Closely**: Watch the first few hours of operation
3. **Regular Updates**: Keep dependencies and prices updated
4. **Backup Strategies**: Have rollback plans ready
5. **Profit Taking**: Regularly withdraw profits

## 🆘 Emergency Procedures

### Stop the Bot
```bash
# Graceful shutdown
Ctrl+C in bot terminal

# Force stop (if needed)
python -c "import sys; sys.exit()" 

# Emergency contract pause (if implemented)
python scripts/emergency_stop.py
```

### Recover Funds
If funds get stuck in the contract:
```bash
python scripts/emergency_withdraw.py
```

## 📈 Performance Optimization

### Improving Profitability
1. **Optimize Gas Settings**: Lower gas prices during off-peak times
2. **Adjust Thresholds**: Fine-tune minimum profit requirements
3. **Add More DEXes**: Increase arbitrage opportunities
4. **Faster Execution**: Optimize code and network connections

### Scaling Up
1. **Increase Trade Size**: After proving profitability
2. **Multiple Pairs**: Trade different token pairs
3. **Cross-Chain**: Expand to other networks
4. **Advanced Strategies**: Implement triangular arbitrage

## 🔄 Maintenance

### Daily Tasks
- Check bot status and logs
- Review performance metrics
- Monitor wallet balance
- Update price feeds if needed

### Weekly Tasks
- Analyze weekly performance
- Update dependencies
- Review and optimize strategies
- Backup important data

### Monthly Tasks
- Security audit of configurations
- Update API keys if needed
- Comprehensive performance review
- Strategy adjustments based on market conditions

## 🌐 Network Configuration

### Polygon Mainnet
- **Network Name**: Polygon Mainnet
- **RPC URL**: https://polygon-rpc.com/
- **Chain ID**: 137
- **Symbol**: MATIC
- **Explorer**: https://polygonscan.com/

### Mumbai Testnet
- **Network Name**: Mumbai Testnet
- **RPC URL**: https://rpc-mumbai.maticvigil.com/
- **Chain ID**: 80001
- **Symbol**: MATIC
- **Explorer**: https://mumbai.polygonscan.com/
- **Faucet**: https://faucet.polygon.technology/

## 📚 Additional Resources

- [Polygon Documentation](https://docs.polygon.technology/)
- [Aave V3 Documentation](https://docs.aave.com/developers/)
- [1inch API Documentation](https://docs.1inch.io/)
- [Hardhat Documentation](https://hardhat.org/docs)
- [Web3.py Documentation](https://web3py.readthedocs.io/)

## ❓ Support

If you encounter issues:

1. **Check Troubleshooting Guide**: See `docs/TROUBLESHOOTING.md`
2. **Review Logs**: Check `logs/arbitrage_bot.log` for errors
3. **Test Configuration**: Verify all settings in `config/.env`
4. **Community Support**: Join our Discord/Telegram community
5. **Create Issue**: Report bugs on GitHub

---

## ⚠️ Important Disclaimers

- **Risk Warning**: Cryptocurrency trading involves significant risk
- **No Guarantees**: Past performance doesn't guarantee future results
- **Start Small**: Always begin with small amounts you can afford to lose
- **Legal Compliance**: Ensure compliance with local regulations
- **Educational Purpose**: This bot is for educational and research purposes

---

**Ready to start your arbitrage journey? Follow this guide step by step and remember: start small, monitor closely, and scale gradually! 🚀**