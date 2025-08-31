# -*- coding: utf-8 -*-
# Configuration management
# config/settings.py

"""
Configuration Management System for Flashloan Arbitrage Bot
Handles environment variables, validation, and settings management
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from decimal import Decimal
import json
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import logging

logger = logging.getLogger('settings')

# Load environment variables
env_path = project_root / 'config' / '.env'
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f"[SUCCESS] Loaded environment from {env_path}")
else:
    logger.warning(f"[WARNING] No .env file found at {env_path}")


@dataclass
class NetworkConfig:
    """Network-specific configuration"""
    name: str
    rpc_url: str
    chain_id: int
    currency_symbol: str
    block_explorer: str
    is_testnet: bool = False


@dataclass
class TradingConfig:
    """Trading strategy configuration"""
    min_profit_threshold: Decimal = Decimal("5.0")  # Minimum $5 profit
    max_trade_size: Decimal = Decimal("10000.0")  # Maximum $10k per trade
    max_flashloan_amount: Decimal = Decimal("50000.0")  # Maximum $50k flashloan
    slippage_tolerance: Decimal = Decimal("0.005")  # 0.5% slippage tolerance
    gas_price_limit: int = 100  # Maximum gas price in gwei
    max_gas_limit: int = 2000000  # Maximum gas limit
    price_impact_limit: Decimal = Decimal("0.03")  # 3% maximum price impact
    execution_timeout: int = 300  # 5 minutes execution timeout


@dataclass
class RiskConfig:
    """Risk management configuration"""
    max_failed_trades: int = 3  # Max consecutive failed trades
    daily_volume_limit: Decimal = Decimal("100000")  # Daily trading volume limit
    emergency_stop_loss: Decimal = Decimal("100.0")  # Emergency stop if loss > $100
    min_wallet_balance: Decimal = Decimal("10.0")  # Minimum MATIC balance required
    position_size_limit: Decimal = Decimal("0.1")  # Max 10% of available capital
    circuit_breaker_cooldown: int = 1800  # 30 minutes cooldown


@dataclass
class APIConfig:
    """External API configuration"""
    coingecko_api_key: Optional[str] = None
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    oneinch_api_key: Optional[str] = None
    oneinch_base_url: str = "https://api.1inch.io/v5.0"
    moralis_api_key: Optional[str] = None
    alchemy_api_key: Optional[str] = None
    rate_limit_requests_per_minute: int = 60
    request_timeout: int = 30
    max_retries: int = 3


@dataclass
class MonitoringConfig:
    """Monitoring and alerting configuration"""
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    discord_username: str = "Flashloan Bot"
    discord_avatar_url: Optional[str] = None
    enable_notifications: bool = True
    notification_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_level: str = "INFO"
    log_file_path: str = "logs/arbitrage_bot.log"
    enable_performance_monitoring: bool = True
    metrics_retention_days: int = 30


@dataclass
class DEXConfig:
    """DEX-specific configuration"""
    enabled_dexes: List[str] = field(default_factory=lambda: [
        "uniswap_v3", "sushiswap", "quickswap", "balancer"
    ])
    uniswap_v3_router: str = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
    sushiswap_router: str = "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"
    quickswap_router: str = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
    balancer_vault: str = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"
    default_fee_tier: int = 3000  # 0.3% for Uniswap V3


@dataclass
class SecurityConfig:
    """Security and safety configuration"""
    enable_testnet: bool = True
    dry_run_mode: bool = True
    require_manual_approval: bool = False
    wallet_address: Optional[str] = None
    private_key: Optional[str] = None
    enable_contract_verification: bool = True
    max_approval_amount: str = "115792089237316195423570985008687907853269984665640564039457584007913129639935"  # uint256 max


class Settings:
    """
    Main settings class that loads and validates all configuration
    """

    def __init__(self):
        self.project_root = project_root
        self.config_dir = project_root / 'config'

        # Load all configuration sections
        self.network = self._load_network_config()
        self.trading = self._load_trading_config()
        self.risk = self._load_risk_config()
        self.api = self._load_api_config()
        self.monitoring = self._load_monitoring_config()
        self.dex = self._load_dex_config()
        self.security = self._load_security_config()

        # Validate configuration
        self._validate_configuration()

        logger.info("[CONFIG] Configuration loaded successfully")
        self._log_configuration_summary()

    def _load_network_config(self) -> NetworkConfig:
        """Load network configuration"""
        network_name = os.getenv('NETWORK', 'polygon').lower()

        networks = {
            'polygon': NetworkConfig(
                name='Polygon Mainnet',
                rpc_url=os.getenv('WEB3_PROVIDER_URL', 'https://polygon-rpc.com/'),
                chain_id=137,
                currency_symbol='MATIC',
                block_explorer='https://polygonscan.com',
                is_testnet=False
            ),
            'mumbai': NetworkConfig(
                name='Mumbai Testnet',
                rpc_url=os.getenv('WEB3_PROVIDER_URL', 'https://rpc-mumbai.maticvigil.com/'),
                chain_id=80001,
                currency_symbol='MATIC',
                block_explorer='https://mumbai.polygonscan.com',
                is_testnet=True
            ),
            'ethereum': NetworkConfig(
                name='Ethereum Mainnet',
                rpc_url=os.getenv('WEB3_PROVIDER_URL', ''),
                chain_id=1,
                currency_symbol='ETH',
                block_explorer='https://etherscan.io',
                is_testnet=False
            )
        }

        if network_name not in networks:
            logger.warning(f"[WARNING] Unknown network {network_name}, defaulting to polygon")
            network_name = 'polygon'

        return networks[network_name]

    def _load_trading_config(self) -> TradingConfig:
        """Load trading configuration"""
        return TradingConfig(
            min_profit_threshold=Decimal(os.getenv('MIN_PROFIT_THRESHOLD', '5.0')),
            max_trade_size=Decimal(os.getenv('MAX_TRADE_SIZE', '10000.0')),
            max_flashloan_amount=Decimal(os.getenv('MAX_FLASHLOAN_AMOUNT', '50000.0')),
            slippage_tolerance=Decimal(os.getenv('SLIPPAGE_TOLERANCE', '0.005')),
            gas_price_limit=int(os.getenv('GAS_PRICE_LIMIT', '100')),
            max_gas_limit=int(os.getenv('MAX_GAS_LIMIT', '2000000')),
            price_impact_limit=Decimal(os.getenv('PRICE_IMPACT_LIMIT', '0.03')),
            execution_timeout=int(os.getenv('EXECUTION_TIMEOUT', '300'))
        )

    def _load_risk_config(self) -> RiskConfig:
        """Load risk management configuration"""
        return RiskConfig(
            max_failed_trades=int(os.getenv('MAX_FAILED_TRADES', '3')),
            daily_volume_limit=Decimal(os.getenv('DAILY_VOLUME_LIMIT', '100000')),
            emergency_stop_loss=Decimal(os.getenv('EMERGENCY_STOP_LOSS', '100.0')),
            min_wallet_balance=Decimal(os.getenv('MIN_WALLET_BALANCE', '10.0')),
            position_size_limit=Decimal(os.getenv('POSITION_SIZE_LIMIT', '0.1')),
            circuit_breaker_cooldown=int(os.getenv('CIRCUIT_BREAKER_COOLDOWN', '1800'))
        )

    def _load_api_config(self) -> APIConfig:
        """Load API configuration"""
        return APIConfig(
            coingecko_api_key=os.getenv('COINGECKO_API_KEY'),
            oneinch_api_key=os.getenv('ONEINCH_API_KEY'),
            moralis_api_key=os.getenv('MORALIS_API_KEY'),
            alchemy_api_key=os.getenv('ALCHEMY_API_KEY'),
            rate_limit_requests_per_minute=int(os.getenv('RATE_LIMIT_RPM', '60')),
            request_timeout=int(os.getenv('REQUEST_TIMEOUT', '30')),
            max_retries=int(os.getenv('MAX_RETRIES', '3'))
        )

    def _load_monitoring_config(self) -> MonitoringConfig:
        """Load monitoring configuration"""
        return MonitoringConfig(
            telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
            telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID'),
            discord_webhook_url=os.getenv('DISCORD_WEBHOOK_URL'),
            discord_username=os.getenv("DISCORD_USERNAME", "Flashloan Bot"),
            discord_avatar_url=os.getenv("DISCORD_AVATAR_URL"),
            enable_notifications=os.getenv('ENABLE_NOTIFICATIONS', 'true').lower() == 'true',
            notification_level=os.getenv('NOTIFICATION_LEVEL', 'INFO'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_file_path=os.getenv('LOG_FILE_PATH', 'logs/arbitrage_bot.log'),
            enable_performance_monitoring=os.getenv('ENABLE_PERFORMANCE_MONITORING', 'true').lower() == 'true',
            metrics_retention_days=int(os.getenv('METRICS_RETENTION_DAYS', '30'))
        )

    def _load_dex_config(self) -> DEXConfig:
        """Load DEX configuration"""
        enabled_dexes_str = os.getenv('ENABLED_DEXES', 'uniswap_v3,sushiswap,quickswap,balancer')
        enabled_dexes = [dex.strip() for dex in enabled_dexes_str.split(',') if dex.strip()]

        return DEXConfig(
            enabled_dexes=enabled_dexes,
            uniswap_v3_router=os.getenv('UNISWAP_V3_ROUTER', '0xE592427A0AEce92De3Edee1F18E0157C05861564'),
            sushiswap_router=os.getenv('SUSHISWAP_ROUTER', '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'),
            quickswap_router=os.getenv('QUICKSWAP_ROUTER', '0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff'),
            balancer_vault=os.getenv('BALANCER_VAULT', '0xBA12222222228d8Ba445958a75a0704d566BF2C8'),
            default_fee_tier=int(os.getenv('DEFAULT_FEE_TIER', '3000'))
        )

    def _load_security_config(self) -> SecurityConfig:
        """Load security configuration"""
        return SecurityConfig(
            enable_testnet=os.getenv('ENABLE_TESTNET', 'true').lower() == 'true',
            dry_run_mode=os.getenv('DRY_RUN_MODE', 'true').lower() == 'true',
            require_manual_approval=os.getenv('REQUIRE_MANUAL_APPROVAL', 'false').lower() == 'true',
            wallet_address=os.getenv('WALLET_ADDRESS'),
            private_key=os.getenv('PRIVATE_KEY'),
            enable_contract_verification=os.getenv('ENABLE_CONTRACT_VERIFICATION', 'true').lower() == 'true'
        )

    def _validate_configuration(self):
        """Validate configuration for critical issues"""
        errors = []
        warnings = []

        # Network validation
        if not self.network.rpc_url:
            errors.append("WEB3_PROVIDER_URL is required")

        # Security validation
        if not self.security.private_key:
            if not self.security.dry_run_mode:
                errors.append("PRIVATE_KEY is required when not in dry run mode")
            else:
                warnings.append("PRIVATE_KEY not set - running in dry run mode only")

        if self.security.private_key:
            if len(self.security.private_key.replace('0x', '')) != 64:
                errors.append("PRIVATE_KEY must be 64 hex characters (32 bytes)")

        # Trading validation
        if self.trading.min_profit_threshold <= 0:
            errors.append("MIN_PROFIT_THRESHOLD must be positive")

        if self.trading.max_trade_size <= 0:
            errors.append("MAX_TRADE_SIZE must be positive")

        if self.trading.slippage_tolerance < 0 or self.trading.slippage_tolerance > 1:
            errors.append("SLIPPAGE_TOLERANCE must be between 0 and 1")

        # API validation
        if not self.api.coingecko_api_key:
            warnings.append("COINGECKO_API_KEY not set - using free tier with limits")

        if not self.api.oneinch_api_key:
            warnings.append("ONEINCH_API_KEY not set - using free tier with limits")

        # Monitoring validation
        if self.monitoring.enable_notifications:
            if not self.monitoring.telegram_bot_token and not self.monitoring.discord_webhook_url:
                warnings.append("Notifications enabled but no Telegram or Discord configured")

        # Log results
        if errors:
            logger.error(f"[ERROR] Configuration errors: {', '.join(errors)}")
            raise ValueError(f"Configuration validation failed: {', '.join(errors)}")

        if warnings:
            for warning in warnings:
                logger.warning(f"[WARNING] {warning}")

    def _log_configuration_summary(self):
        """Log configuration summary"""
        logger.info("[CONFIG] Configuration Summary:")
        logger.info(f"  [NETWORK] Network: {self.network.name} ({'TESTNET' if self.network.is_testnet else 'MAINNET'})")
        logger.info(f"  [PROFIT] Min Profit: ${self.trading.min_profit_threshold}")
        logger.info(f"  [TRADE] Max Trade: ${self.trading.max_trade_size}")
        logger.info(f"  [TARGET] Slippage: {self.trading.slippage_tolerance:.2%}")
        logger.info(f"  [RISK] Risk Mode: {'DRY RUN' if self.security.dry_run_mode else 'LIVE TRADING'}")
        logger.info(f"  [DEXES] DEXes: {', '.join(self.dex.enabled_dexes)}")

        if self.security.dry_run_mode:
            logger.warning("[SAFE] DRY RUN MODE - No real trades will be executed")
        if self.network.is_testnet:
            logger.warning("[SAFE] TESTNET MODE - Using testnet contracts and tokens")

    def get_contract_address(self, contract_name: str) -> Optional[str]:
        """Get contract address for current network"""
        try:
            # Try to load addresses from addresses.py
            addresses_file = self.config_dir / 'addresses.py'
            if addresses_file.exists():
                spec = {}
                exec(addresses_file.read_text(), spec)

                network_addresses = spec.get(f'{self.network.name.lower()}_addresses', {})
                return network_addresses.get(contract_name)

            return None

        except Exception as e:
            logger.warning(f"[WARNING] Could not load contract address for {contract_name}: {e}")
            return None

    def save_contract_address(self, contract_name: str, address: str):
        """Save contract address to addresses.py"""
        try:
            addresses_file = self.config_dir / 'addresses.py'

            # Load existing addresses
            addresses_data = {}
            if addresses_file.exists():
                spec = {}
                exec(addresses_file.read_text(), spec)
                addresses_data = {k: v for k, v in spec.items() if not k.startswith('__')}

            # Update addresses
            network_key = f'{self.network.name.lower().replace(" ", "_")}_addresses'
            if network_key not in addresses_data:
                addresses_data[network_key] = {}

            addresses_data[network_key][contract_name] = address

            # Write back to file
            with open(addresses_file, 'w') as f:
                f.write("# Contract addresses by network\n")
                f.write("# Auto-generated by settings.py\n\n")

                for network, contracts in addresses_data.items():
                    f.write(f"{network} = {{\n")
                    for contract, addr in contracts.items():
                        f.write(f'    "{contract}": "{addr}",\n')
                    f.write("}\n\n")

            logger.info(f"[SUCCESS] Saved {contract_name} address: {address}")

        except Exception as e:
            logger.error(f"[ERROR] Failed to save contract address: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary (excluding sensitive data)"""
        return {
            'network': {
                'name': self.network.name,
                'chain_id': self.network.chain_id,
                'is_testnet': self.network.is_testnet
            },
            'trading': {
                'min_profit_threshold': str(self.trading.min_profit_threshold),
                'max_trade_size': str(self.trading.max_trade_size),
                'slippage_tolerance': str(self.trading.slippage_tolerance)
            },
            'security': {
                'dry_run_mode': self.security.dry_run_mode,
                'enable_testnet': self.security.enable_testnet,
                'has_private_key': bool(self.security.private_key)
            },
            'dex': {
                'enabled_dexes': self.dex.enabled_dexes
            }
        }


# Global settings instance
_settings_instance: Optional[Settings] = None


def load_settings() -> Settings:
    """Load and return global settings instance"""
    global _settings_instance

    if _settings_instance is None:
        _settings_instance = Settings()

    return _settings_instance


def reload_settings() -> Settings:
    """Reload settings from environment"""
    global _settings_instance
    _settings_instance = None
    return load_settings()


# Convenience functions
def get_network_config() -> NetworkConfig:
    """Get network configuration"""
    return load_settings().network


def get_trading_config() -> TradingConfig:
    """Get trading configuration"""
    return load_settings().trading


def get_risk_config() -> RiskConfig:
    """Get risk configuration"""
    return load_settings().risk


def get_contract_address(contract_name: str) -> Optional[str]:
    """Get contract address for current network"""
    return load_settings().get_contract_address(contract_name)


def is_testnet() -> bool:
    """Check if running on testnet"""
    return load_settings().network.is_testnet


def is_dry_run() -> bool:
    """Check if running in dry run mode"""
    return load_settings().security.dry_run_mode


# Export main classes and functions
__all__ = [
    'Settings', 'NetworkConfig', 'TradingConfig', 'RiskConfig',
    'APIConfig', 'MonitoringConfig', 'DEXConfig', 'SecurityConfig',
    'load_settings', 'reload_settings', 'get_network_config',
    'get_trading_config', 'get_risk_config', 'get_contract_address',
    'is_testnet', 'is_dry_run'
]
