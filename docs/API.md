# API documentation 
# docs/API.md

# 📡 Flashloan Arbitrage Bot - API Documentation

This document provides comprehensive API documentation for all components of the Flashloan Arbitrage Bot system.

## 📋 Table of Contents

- [Bot Core API](#bot-core-api)
- [Smart Contract Interface](#smart-contract-interface)
- [Price Feeds API](#price-feeds-api)
- [Risk Manager API](#risk-manager-api)
- [Monitoring API](#monitoring-api)
- [Configuration API](#configuration-api)
- [Utility Functions](#utility-functions)
- [Event System](#event-system)

---

## 🤖 Bot Core API

### FlashloanArbitrageBot

The main bot class that orchestrates all arbitrage operations.

#### Class: `FlashloanArbitrageBot`

```python
from bot.arbitrage_bot import FlashloanArbitrageBot

bot = FlashloanArbitrageBot()
```

#### Methods

##### `async start_bot()`
Starts the main bot operation loop.

**Returns:** `None`

**Raises:** 
- `ConnectionError`: If unable to connect to blockchain
- `ConfigurationError`: If configuration is invalid

**Example:**
```python
await bot.start_bot()
```

##### `stop_bot()`
Gracefully stops the bot operation.

**Returns:** `None`

**Example:**
```python
bot.stop_bot()
```

##### `get_status()`
Returns current bot status information.

**Returns:** `Dict[str, Any]`
```python
{
    'running': bool,
    'total_trades': int,
    'successful_trades': int,
    'total_profit': float,
    'uptime': timedelta,
    'last_opportunity': datetime
}
```

##### `emergency_stop()`
Immediately stops all bot operations and cancels pending transactions.

**Returns:** `None`

---

## 🔍 Opportunity Scanner API

### OpportunityScanner

Detects arbitrage opportunities across different DEXes.

#### Class: `OpportunityScanner`

```python
from bot.opportunity_scanner import OpportunityScanner

scanner = OpportunityScanner()
```

#### Methods

##### `async scan_opportunities()`
Scans all configured DEXes for arbitrage opportunities.

**Returns:** `List[ArbitrageOpportunity]`

**Example:**
```python
opportunities = await scanner.scan_opportunities()
for opportunity in opportunities:
    print(f"Profit: ${opportunity.profit_usd}")
```

##### `async get_dex_prices(token_pair: str)`
Gets current prices for a token pair across all DEXes.

**Parameters:**
- `token_pair` (str): Token pair (e.g., "USDC/WETH")

**Returns:** `Dict[str, PriceData]`

**Example:**
```python
prices = await scanner.get_dex_prices("USDC/WETH")
print(f"Uniswap price: ${prices['uniswap'].price}")
```

##### `calculate_profit_potential(opportunity: ArbitrageOpportunity, amount: float)`
Calculates potential profit for a specific trade amount.

**Parameters:**
- `opportunity` (ArbitrageOpportunity): The opportunity to analyze
- `amount` (float): Trade amount in USD

**Returns:** `ProfitAnalysis`

### Data Classes

#### `ArbitrageOpportunity`
```python
@dataclass
class ArbitrageOpportunity:
    token_pair: str
    dex_buy: str
    dex_sell: str
    buy_price: float
    sell_price: float
    price_difference: float
    profit_percentage: float
    profit_usd: float
    max_trade_size: float
    estimated_gas_cost: float
    timestamp: datetime
```

#### `PriceData`
```python
@dataclass
class PriceData:
    dex: str
    token_pair: str
    price: float
    liquidity: float
    timestamp: datetime
    bid: float
    ask: float
```

---

## 💰 Price Feeds API

### PriceAggregator

Aggregates price data from multiple sources.

#### Class: `PriceAggregator`

```python
from bot.price_feeds import PriceAggregator

aggregator = PriceAggregator()
```

#### Methods

##### `async get_token_price(token: str, vs_currency: str = "usd")`
Gets current token price from aggregated sources.

**Parameters:**
- `token` (str): Token symbol or address
- `vs_currency` (str): Quote currency (default: "usd")

**Returns:** `TokenPrice`

**Example:**
```python
price = await aggregator.get_token_price("WETH", "usd")
print(f"WETH price: ${price.price}")
```

##### `async get_dex_price(dex: str, token_pair: str)`
Gets specific DEX price for a token pair.

**Parameters:**
- `dex` (str): DEX identifier ("uniswap", "sushiswap", etc.)
- `token_pair` (str): Token pair ("USDC/WETH")

**Returns:** `DexPriceData`

##### `subscribe_to_price_updates(token: str, callback: Callable)`
Subscribes to real-time price updates.

**Parameters:**
- `token` (str): Token to monitor
- `callback` (Callable): Function to call on price update

**Returns:** `str` (subscription_id)

---

## ⚖️ Risk Manager API

### RiskManager

Manages risk and validates trade safety.

#### Class: `RiskManager`

```python
from bot.risk_manager import RiskManager

risk_manager = RiskManager()
```

#### Methods

##### `validate_opportunity(opportunity: ArbitrageOpportunity)`
Validates if an opportunity meets risk criteria.

**Parameters:**
- `opportunity` (ArbitrageOpportunity): Opportunity to validate

**Returns:** `RiskAssessment`

**Example:**
```python
assessment = risk_manager.validate_opportunity(opportunity)
if assessment.approved:
    print("Trade approved!")
```

##### `calculate_optimal_size(opportunity: ArbitrageOpportunity)`
Calculates optimal trade size based on risk parameters.

**Returns:** `float` (optimal trade amount in USD)

##### `check_wallet_balance()`
Checks if wallet has sufficient funds for operations.

**Returns:** `WalletStatus`

#### Data Classes

##### `RiskAssessment`
```python
@dataclass
class RiskAssessment:
    approved: bool
    risk_score: float
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    warnings: List[str]
    max_recommended_size: float
    reasons: List[str]
```

---

## 🔗 Smart Contract Interface API

### ContractInterface

Interface for interacting with the deployed smart contract.

#### Class: `ContractInterface`

```python
from bot.contract_interface import ContractInterface

contract = ContractInterface()
```

#### Methods

##### `async execute_arbitrage(opportunity: ArbitrageOpportunity, amount: float)`
Executes arbitrage trade through the smart contract.

**Parameters:**
- `opportunity` (ArbitrageOpportunity): Trade opportunity
- `amount` (float): Trade amount

**Returns:** `TransactionResult`

**Example:**
```python
result = await contract.execute_arbitrage(opportunity, 1000.0)
if result.success:
    print(f"Trade successful! Profit: ${result.profit}")
```

##### `get_contract_balance()`
Gets current contract balance.

**Returns:** `Dict[str, float]` (token balances)

##### `emergency_withdraw(token: str, amount: float)`
Emergency withdrawal function.

**Parameters:**
- `token` (str): Token address
- `amount` (float): Amount to withdraw

**Returns:** `TransactionResult`

#### Data Classes

##### `TransactionResult`
```python
@dataclass
class TransactionResult:
    success: bool
    transaction_hash: str
    gas_used: int
    gas_price: int
    profit: float
    error_message: Optional[str]
    execution_time: float
```

---

## 📊 Monitoring API

### PerformanceMonitor

Monitors bot performance and generates metrics.

#### Class: `PerformanceMonitor`

```python
from scripts.monitor_performance import PerformanceMonitor

monitor = PerformanceMonitor()
```

#### Methods

##### `get_performance_metrics(period: str = "24h")`
Gets performance metrics for a specific period.

**Parameters:**
- `period` (str): Time period ("1h", "24h", "7d", "30d")

**Returns:** `PerformanceMetrics`

##### `get_trade_history(limit: int = 100)`
Gets recent trade history.

**Parameters:**
- `limit` (int): Maximum number of trades to return

**Returns:** `List[TradeRecord]`

##### `generate_report(start_date: datetime, end_date: datetime)`
Generates performance report for date range.

**Returns:** `PerformanceReport`

---

## ⚙️ Configuration API

### Settings

Configuration management system.

#### Functions

##### `load_settings()`
Loads configuration from environment variables and config files.

**Returns:** `BotSettings`

**Example:**
```python
from config.settings import load_settings

settings = load_settings()
print(f"Min profit threshold: ${settings.min_profit_threshold}")
```

##### `update_setting(key: str, value: Any)`
Updates a configuration setting.

**Parameters:**
- `key` (str): Setting key
- `value` (Any): New value

**Returns:** `bool` (success)

#### Data Classes

##### `BotSettings`
```python
@dataclass
class BotSettings:
    # Trading settings
    min_profit_threshold: float
    max_trade_size: float
    slippage_tolerance: float
    gas_price_limit: int
    
    # Network settings
    network: str
    web3_provider_url: str
    
    # API settings
    coingecko_api_key: str
    oneinch_api_key: str
    
    # Risk settings
    max_failed_trades: int
    enable_testnet: bool
    dry_run_mode: bool
```

---

## 🛠️ Utility Functions

### Logger

Custom logging system with colored output.

#### Functions

##### `get_logger(name: str)`
Gets a configured logger instance.

**Parameters:**
- `name` (str): Logger name

**Returns:** `CustomLogger`

**Example:**
```python
from bot.utils.logger import get_logger

logger = get_logger('my_module')
logger.info("Bot started")
logger.success("Trade completed successfully")
logger.warning("Low balance detected")
logger.error("Connection failed")
```

### Helpers

Common utility functions.

#### Functions

##### `wei_to_ether(wei_amount: int)`
Converts Wei to Ether.

**Parameters:**
- `wei_amount` (int): Amount in Wei

**Returns:** `float`

##### `ether_to_wei(ether_amount: float)`
Converts Ether to Wei.

**Parameters:**
- `ether_amount` (float): Amount in Ether

**Returns:** `int`

##### `format_currency(amount: float, currency: str = "USD")`
Formats currency for display.

**Returns:** `str`

##### `calculate_percentage_change(old_value: float, new_value: float)`
Calculates percentage change between two values.

**Returns:** `float`

---

## 🎯 Event System

### Event Types

The bot uses an event-driven architecture with the following events:

#### `OpportunityFoundEvent`
```python
{
    'type': 'opportunity_found',
    'opportunity': ArbitrageOpportunity,
    'timestamp': datetime
}
```

#### `TradeExecutedEvent`
```python
{
    'type': 'trade_executed',
    'opportunity': ArbitrageOpportunity,
    'result': TransactionResult,
    'timestamp': datetime
}
```

#### `ErrorEvent`
```python
{
    'type': 'error',
    'error_type': str,
    'message': str,
    'traceback': str,
    'timestamp': datetime
}
```

### Event Handlers

#### Subscribing to Events

```python
from bot.events import EventBus

def on_opportunity_found(event):
    print(f"New opportunity: ${event['opportunity'].profit_usd}")

EventBus.subscribe('opportunity_found', on_opportunity_found)
```

#### Publishing Events

```python
EventBus.publish('custom_event', {
    'type': 'custom_event',
    'data': {'key': 'value'},
    'timestamp': datetime.now()
})
```

---

## 🔌 Integration Examples

### Basic Bot Setup

```python
import asyncio
from bot.arbitrage_bot import FlashloanArbitrageBot
from bot.utils.logger import get_logger

async def main():
    logger = get_logger('main')
    bot = FlashloanArbitrageBot()
    
    try:
        logger.info("Starting arbitrage bot...")
        await bot.start_bot()
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
        bot.stop_bot()
    except Exception as e:
        logger.error(f"Bot error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Custom Strategy Implementation

```python
from bot.opportunity_scanner import OpportunityScanner
from bot.risk_manager import RiskManager

class CustomStrategy:
    def __init__(self):
        self.scanner = OpportunityScanner()
        self.risk_manager = RiskManager()
    
    async def find_opportunities(self):
        opportunities = await self.scanner.scan_opportunities()
        
        # Filter opportunities using custom logic
        filtered = []
        for opp in opportunities:
            assessment = self.risk_manager.validate_opportunity(opp)
            if assessment.approved and opp.profit_percentage > 2.0:
                filtered.append(opp)
        
        return filtered
```

### Price Monitoring

```python
from bot.price_feeds import PriceAggregator

async def monitor_prices():
    aggregator = PriceAggregator()
    
    def price_update_callback(token, new_price):
        print(f"{token} price updated: ${new_price}")
    
    # Subscribe to WETH price updates
    subscription_id = aggregator.subscribe_to_price_updates(
        "WETH", 
        price_update_callback
    )
    
    # Keep monitoring
    await asyncio.sleep(3600)  # 1 hour
```

---

## 📝 Error Codes

### Bot Error Codes

| Code | Description |
|------|-------------|
| `BOT_001` | Configuration error |
| `BOT_002` | Connection to blockchain failed |
| `BOT_003` | Insufficient funds |
| `BOT_004` | Trade execution failed |
| `BOT_005` | Emergency stop activated |

### Contract Error Codes

| Code | Description |
|------|-------------|
| `CONTRACT_001` | Flashloan failed |
| `CONTRACT_002` | Slippage too high |
| `CONTRACT_003` | Insufficient liquidity |
| `CONTRACT_004` | Trade not profitable |
| `CONTRACT_005` | Gas limit exceeded |

---

## 🚀 API Rate Limits

### External APIs

| Service | Rate Limit | Notes |
|---------|------------|-------|
| CoinGecko | 50 calls/min | Free tier |
| 1inch | 100 calls/min | With API key |
| Polygon RPC | 1000 calls/min | Depends on provider |

### Best Practices

1. **Caching**: Cache price data for 5-10 seconds
2. **Batching**: Batch multiple requests when possible
3. **Error Handling**: Implement exponential backoff
4. **Monitoring**: Track API usage and limits

---

## 🔒 Security Considerations

### API Key Management
- Store API keys in environment variables
- Use different keys for different environments
- Regularly rotate API keys
- Monitor API key usage

### Smart Contract Security
- Validate all inputs
- Use reentrancy guards
- Implement emergency stop functions
- Regular security audits

### Network Security
- Use HTTPS/WSS connections
- Validate all external data
- Implement timeout mechanisms
- Monitor for anomalous behavior

---

**This API documentation is constantly updated. Check the latest version in the repository for the most current information.**