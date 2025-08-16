# Common issues 
# docs/TROUBLESHOOTING.md

# 🛠️ Flashloan Arbitrage Bot - Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the Flashloan Arbitrage Bot.

## 📋 Table of Contents

- [Quick Diagnostic Checklist](#quick-diagnostic-checklist)
- [Common Setup Issues](#common-setup-issues)
- [Bot Runtime Issues](#bot-runtime-issues)
- [Smart Contract Issues](#smart-contract-issues)
- [Network & Connection Issues](#network--connection-issues)
- [Performance Issues](#performance-issues)
- [Error Code Reference](#error-code-reference)
- [Advanced Troubleshooting](#advanced-troubleshooting)
- [Getting Support](#getting-support)

---

## ✅ Quick Diagnostic Checklist

Before diving into specific issues, run through this checklist:

### 🔍 Basic Checks
- [ ] Python 3.8+ installed (`python --version`)
- [ ] Node.js 16+ installed (`node --version`)
- [ ] Virtual environment activated
- [ ] All dependencies installed (`pip list`)
- [ ] `.env` file exists and configured
- [ ] Wallet has MATIC for gas fees
- [ ] Internet connection stable

### ⚙️ Configuration Checks
- [ ] `WEB3_PROVIDER_URL` is valid and working
- [ ] `PRIVATE_KEY` is correct (64 hex characters)
- [ ] API keys are active and have quota
- [ ] Contract addresses are correct for your network
- [ ] Trading parameters are reasonable

### 🔗 Connection Checks
```bash
# Test Web3 connection
python -c "from web3 import Web3; w3 = Web3(Web3.HTTPProvider('YOUR_RPC_URL')); print(f'Connected: {w3.isConnected()}')"

# Test wallet balance
python -c "from config.settings import load_settings; from web3 import Web3; settings = load_settings(); w3 = Web3(Web3.HTTPProvider(settings.web3_provider_url)); print(f'Balance: {w3.eth.get_balance(w3.eth.account.from_key(settings.private_key).address)}')"
```

---

## 🚨 Common Setup Issues

### Issue: "ModuleNotFoundError" when importing

**Symptoms:**
```
ModuleNotFoundError: No module named 'web3'
ImportError: No module named 'bot'
```

**Solutions:**

1. **Check Virtual Environment:**
```bash
# Verify you're in the virtual environment
which python  # Should show venv path

# If not activated:
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
```

2. **Reinstall Dependencies:**
```bash
pip install -r requirements.txt --force-reinstall
```

3. **Check Python Path:**
```bash
python -c "import sys; print('\n'.join(sys.path))"
```

### Issue: ".env file not found" or configuration errors

**Symptoms:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'config/.env'
ConfigurationError: Missing required environment variable
```

**Solutions:**

1. **Create .env file:**
```bash
cp config/.env.template config/.env
```

2. **Verify .env location:**
```bash
ls -la config/
# Should show .env file
```

3. **Check .env format:**
```bash
# Ensure no spaces around =
WEB3_PROVIDER_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
# NOT: WEB3_PROVIDER_URL = https://...
```

### Issue: Smart contract deployment fails

**Symptoms:**
```
Error: Failed to deploy contract
ValueError: {'code': -32000, 'message': 'insufficient funds for gas * price + value'}
```

**Solutions:**

1. **Check wallet balance:**
```bash
python scripts/check_balance.py
```

2. **Reduce gas price:**
```javascript
// In hardhat.config.js
gasPrice: 30000000000, // 30 gwei instead of higher
```

3. **Use testnet first:**
```bash
# In .env
NETWORK=mumbai
ENABLE_TESTNET=true
```

---

## 🤖 Bot Runtime Issues

### Issue: Bot starts but finds no opportunities

**Symptoms:**
```
INFO: Bot started successfully
INFO: Scanning for opportunities...
INFO: No profitable opportunities found
```

**Diagnosis & Solutions:**

1. **Check profit thresholds:**
```python
# In config/.env - lower the threshold temporarily
MIN_PROFIT_THRESHOLD=1.0  # Instead of 5.0
```

2. **Verify DEX connections:**
```python
python -c "from bot.price_feeds import PriceAggregator; import asyncio; asyncio.run(PriceAggregator().test_connections())"
```

3. **Check market volatility:**
```bash
# Monitor price differences manually
python scripts/market_analysis.py
```

4. **Test with dry run:**
```python
# In .env
DRY_RUN_MODE=true
```

### Issue: Bot stops with "Insufficient funds" error

**Symptoms:**
```
ERROR: Insufficient funds for trade
ERROR: Wallet balance too low for gas fees
```

**Solutions:**

1. **Check all balances:**
```bash
python scripts/check_balance.py --detailed
```

2. **Reduce trade size:**
```python
# In .env
MAX_TRADE_SIZE=100.0  # Reduce from 1000.0
```

3. **Get more MATIC:**
```bash
# For testnet
https://faucet.polygon.technology/
# For mainnet - buy MATIC and bridge to Polygon
```

### Issue: High gas fees eating profits

**Symptoms:**
```
WARNING: Gas cost $15 exceeds profit $10
INFO: Trade skipped due to high gas cost
```

**Solutions:**

1. **Optimize gas settings:**
```python
# In .env
GAS_PRICE_LIMIT=50  # Lower limit in gwei
```

2. **Increase minimum profit:**
```python
MIN_PROFIT_THRESHOLD=20.0  # Ensure profit > gas
```

3. **Trade during off-peak hours:**
```python
# Add time-based trading in bot logic
import datetime
current_hour = datetime.datetime.now().hour
if 2 <= current_hour <= 8:  # Low traffic hours
    # Execute trades
```

---

## 📊 Smart Contract Issues

### Issue: Contract calls fail with "execution reverted"

**Symptoms:**
```
ValueError: execution reverted: FlashloanArbitrage: Trade not profitable
web3.exceptions.ContractLogicError
```

**Solutions:**

1. **Check contract state:**
```python
python scripts/contract_debug.py
```

2. **Verify token approvals:**
```python
# Check if tokens are approved for contract
python scripts/check_approvals.py
```

3. **Test with smaller amounts:**
```python
# Reduce trade size to test
amount = 100  # Instead of 1000
```

### Issue: Flashloan fails

**Symptoms:**
```
Error: FlashloanCallback: Flashloan failed
Error: Aave flashloan execution failed
```

**Diagnosis & Solutions:**

1. **Check Aave pool status:**
```python
python scripts/check_aave_status.py
```

2. **Verify flashloan parameters:**
```solidity
// Ensure amounts are within limits
require(amount <= maxFlashloanAmount, "Amount too large");
```

3. **Test flashloan isolation:**
```bash
# Test just the flashloan without arbitrage
npx hardhat test test/flashloan-only.js
```

---

## 🌐 Network & Connection Issues

### Issue: "Connection timeout" or "Network unreachable"

**Symptoms:**
```
requests.exceptions.ConnectTimeout
ConnectionError: HTTPSConnectionPool
WebSocketTimeoutException
```

**Solutions:**

1. **Test RPC endpoint:**
```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
```

2. **Switch RPC provider:**
```python
# In .env - try different providers
WEB3_PROVIDER_URL=https://rpc-mainnet.matic.network
# OR
WEB3_PROVIDER_URL=https://polygon-rpc.com/
```

3. **Increase timeout values:**
```python
# In bot/contract_interface.py
w3 = Web3(Web3.HTTPProvider(
    provider_url, 
    request_kwargs={'timeout': 60}
))
```

### Issue: "Invalid API Key" errors

**Symptoms:**
```
Unauthorized: Invalid API key
403 Forbidden: API key required
```

**Solutions:**

1. **Verify API keys:**
```bash
# Test CoinGecko API
curl "https://api.coingecko.com/api/v3/ping" \
  -H "x-cg-demo-api-key: YOUR_API_KEY"

# Test 1inch API  
curl "https://api.1inch.io/v5.0/137/healthcheck" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

2. **Regenerate API keys:**
- Go to provider websites
- Generate new keys
- Update .env file

3. **Check rate limits:**
```python
python scripts/check_api_limits.py
```

---

## 📈 Performance Issues

### Issue: Bot runs slowly or misses opportunities

**Symptoms:**
```
WARNING: Opportunity scan took 15 seconds
WARNING: Price data stale (30s old)
INFO: Missed arbitrage opportunity - too slow
```

**Solutions:**

1. **Optimize scanning frequency:**
```python
# In arbitrage_bot.py
SCAN_INTERVAL = 2  # Reduce from 5 seconds
```

2. **Enable price caching:**
```python
# In price_feeds.py
ENABLE_PRICE_CACHE = True
CACHE_DURATION = 3  # seconds
```

3. **Use WebSocket connections:**
```python
# Switch from HTTP to WebSocket for faster updates
WEB3_PROVIDER_URL=wss://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
```

4. **Parallel processing:**
```python
import asyncio
# Use asyncio.gather for concurrent price fetching
prices = await asyncio.gather(*[
    get_dex_price(dex, pair) for dex in DEXES
])
```

### Issue: High memory usage or memory leaks

**Symptoms:**
```
WARNING: Memory usage: 85%
MemoryError: Unable to allocate array
```

**Solutions:**

1. **Monitor memory usage:**
```python
python scripts/memory_profiler.py
```

2. **Clear old data:**
```python
# In bot logic, limit data retention
MAX_PRICE_HISTORY = 1000  # Keep only recent data
```

3. **Restart bot periodically:**
```bash
# Add to cron job - restart daily
0 2 * * * /path/to/restart_bot.sh
```

---

## 🔍 Error Code Reference

### Bot Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `BOT_001` | Configuration missing | Check .env file |
| `BOT_002` | Blockchain connection failed | Verify RPC URL |
| `BOT_003` | Insufficient wallet funds | Add MATIC to wallet |
| `BOT_004` | Trade execution failed | Check contract state |
| `BOT_005` | Emergency stop activated | Review logs, restart manually |

### Contract Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `CONTRACT_001` | Flashloan callback failed | Check Aave pool status |
| `CONTRACT_002` | Slippage exceeded limit | Increase slippage tolerance |
| `CONTRACT_003` | Insufficient DEX liquidity | Reduce trade size |
| `CONTRACT_004` | Trade not profitable after execution | Increase profit threshold |
| `CONTRACT_005` | Gas estimation failed | Increase gas limit |

### Network Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `NET_001` | RPC timeout | Switch provider or increase timeout |
| `NET_002` | Rate limit exceeded | Implement backoff or get higher tier |
| `NET_003` | Invalid response format | Update Web3.py version |
| `NET_004` | Websocket disconnected | Implement reconnection logic |

---

## 🔧 Advanced Troubleshooting

### Debug Mode

Enable detailed logging:

```python
# In .env
LOG_LEVEL=DEBUG
ENABLE_DETAILED_LOGGING=true
```

View detailed logs:
```bash
tail -f logs/arbitrage_bot.log | grep DEBUG
```

### Transaction Debugging

1. **Enable transaction tracing:**
```python
# In contract_interface.py
tx_hash = contract.functions.executeArbitrage(...).transact()
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
print(f"Gas used: {receipt.gasUsed}")
```

2. **Analyze failed transactions:**
```python
python scripts/analyze_failed_tx.py --hash 0x1234...
```

### Performance Profiling

```python
# Add profiling to bot
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
# ... bot operations ...
profiler.disable()

stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats()
```

### Memory Debugging

```python
# Install memory profiler
pip install memory-profiler

# Profile memory usage
python -m memory_profiler bot/arbitrage_bot.py
```

---

## 🆘 Emergency Procedures

### Emergency Stop

If bot is malfunctioning:

1. **Immediate stop:**
```bash
# Kill bot process
pkill -f "python.*arbitrage_bot"
```

2. **Contract emergency stop:**
```python
python scripts/emergency_stop.py
```

3. **Withdraw all funds:**
```python
python scripts/emergency_withdraw.py
```

### Recovery Procedures

1. **Backup current state:**
```bash
cp logs/arbitrage_bot.log logs/backup_$(date +%Y%m%d_%H%M%S).log
cp data/ backup_data/ -r
```

2. **Reset to known good state:**
```bash
git stash
git checkout main
git pull origin main
python scripts/setup_environment.py
```

3. **Restore configuration:**
```bash
# Restore your .env file from backup
cp backup/.env config/.env
```

---

## 📊 Health Check Script

Create a comprehensive health check:

```python
# scripts/health_check.py
import asyncio
from bot.arbitrage_bot import FlashloanArbitrageBot
from bot.utils.logger import get_logger

async def health_check():
    logger = get_logger('health_check')
    
    checks = {
        'web3_connection': False,
        'wallet_balance': False,
        'contract_deployed': False,
        'api_keys_valid': False,
        'price_feeds_working': False
    }
    
    # Perform checks
    try:
        # Web3 connection
        from web3 import Web3
        from config.settings import load_settings
        settings = load_settings()
        w3 = Web3(Web3.HTTPProvider(settings.web3_provider_url))
        checks['web3_connection'] = w3.isConnected()
        
        # Wallet balance
        account = w3.eth.account.from_key(settings.private_key)
        balance = w3.eth.get_balance(account.address)
        checks['wallet_balance'] = balance > w3.toWei(1, 'ether')  # At least 1 MATIC
        
        # Test other components...
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
    
    # Report results
    for check, status in checks.items():
        status_icon = "✅" if status else "❌"
        logger.info(f"{status_icon} {check}: {'PASS' if status else 'FAIL'}")
    
    return all(checks.values())

if __name__ == "__main__":
    asyncio.run(health_check())
```

Run health check:
```bash
python scripts/health_check.py
```

---

## 🆘 Getting Support

### Self-Help Resources

1. **Check logs first:**
```bash
# Recent errors
tail -100 logs/arbitrage_bot.log | grep ERROR

# Specific timeframe
grep "2024-01-15 14:" logs/arbitrage_bot.log
```

2. **Run diagnostics:**
```bash
python scripts/health_check.py
python scripts/diagnose_issues.py
```

3. **Test individual components:**
```bash
python -m pytest tests/ -v -k "test_specific_function"
```

### Creating Support Requests

When reporting issues, include:

1. **Environment information:**
```bash
python --version
pip list > requirements_installed.txt
```

2. **Configuration (sanitized):**
```bash
# Remove private keys and API keys before sharing
cat config/.env | sed 's/=.*/=***REDACTED***/'
```

3. **Error logs:**
```bash
tail -200 logs/arbitrage_bot.log > error_log.txt
```

4. **System information:**
```bash
uname -a  # Linux/macOS
# or
systeminfo  # Windows
```

### Community Support

- **Discord**: Join our Discord server for real-time help
- **Telegram**: Join our Telegram group for quick questions
- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Check docs/ folder for detailed guides

### Professional Support

For production deployments:
- **Audit Services**: Smart contract security audits
- **Consulting**: Custom strategy development
- **Managed Hosting**: Fully managed bot hosting
- **24/7 Support**: Enterprise support packages

---

## 📝 Troubleshooting Log Template

When troubleshooting, keep a log:

```
Issue: [Brief description]
Date: [YYYY-MM-DD HH:MM]
Environment: [testnet/mainnet]
Bot Version: [version]

Symptoms:
- [What you observed]
- [Error messages]
- [Unexpected behavior]

Steps Taken:
1. [Action taken]
2. [Result]
3. [Next action]

Resolution:
[How the issue was resolved]

Prevention:
[How to prevent this in the future]
```

---

**Remember: Most issues have simple solutions. Work through the checklist systematically, and don't hesitate to start with the basics! 🛠️**