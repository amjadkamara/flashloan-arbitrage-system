# config/addresses.py
"""
Polygon Mainnet Contract Addresses
Centralized address management for all protocol contracts
"""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal

# =============================================================================
# CORE TOKEN ADDRESSES (Polygon Mainnet)
# =============================================================================

POLYGON_ADDRESSES = {
    # Major Stablecoins
    "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # USD Coin
    "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",  # Tether USD
    "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",  # MakerDAO DAI

    # Native & Wrapped Tokens
    "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",  # Wrapped MATIC
    "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",  # Wrapped Ethereum
    "WBTC": "0x1bfd67037b42cf73acf2047067bd4f2c47d9bfd6",  # Wrapped Bitcoin

    # Other Major Tokens
    "LINK": "0x53E0bca35eC356BD5ddDFebbD1Fc0fD03FaBad39",  # Chainlink
    "AAVE": "0xD6DF932A45C0f255f85145f286eA0b292B21C90B",  # Aave Token
    "CRV": "0x172370d5cd63279efa6d502dab29171933a610af",  # Curve
    "SUSHI": "0x0b3F868E0BE5597D5DB7fEB59E1CADBb0fdDa50a",  # SushiSwap

    # Polygon Ecosystem Tokens
    "QUICK": "0x831753DD7087CaC61aB5644b308642cc1c33Dc13",  # QuickSwap
    "GHST": "0x385Eeac5cB85A38A9a07A70c73e0a3271CfB54A7",  # Aavegotchi
}

# =============================================================================
# AAVE V3 PROTOCOL ADDRESSES
# =============================================================================

AAVE_ADDRESSES = {
    "POOL": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
    "PROVIDER": "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
    "ORACLE": "0xb023e699F5a33916Ea823A16485e259257cA8Bd1",
    "REWARDS_CONTROLLER": "0x929EC64c34a17401F460460D4B9390518E5B473e",
    "WETH_GATEWAY": "0x1e4b7A6b903680eab0c5dAbcb8fD429cD2a9598c",
}

# =============================================================================
# DEX ROUTER ADDRESSES
# =============================================================================

DEX_ADDRESSES = {
    # QuickSwap (Uniswap V2 Fork) - Most liquid DEX on Polygon
    "QUICKSWAP_ROUTER": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
    "QUICKSWAP_FACTORY": "0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32",

    # SushiSwap
    "SUSHISWAP_ROUTER": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
    "SUSHISWAP_FACTORY": "0xc35DADB65012eC5796536bD9864eD8773aBc74C4",

    # Uniswap V3
    "UNISWAP_V3_ROUTER": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
    "UNISWAP_V3_FACTORY": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    "UNISWAP_V3_QUOTER": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6",
    "UNISWAP_V3_NFT_MANAGER": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",

    # 1inch Aggregator
    "ONE_INCH_ROUTER": "0x1111111254EEB25477B68fb85Ed929f73A960582",
    "ONE_INCH_ORACLE": "0x7F069df72b7A39bCE9806e3AfaF579E54D8CF2b9",

    # Curve Finance
    "CURVE_ADDRESS_PROVIDER": "0x0000000022D53366457F9d5E68Ec105046FC4383",
    "CURVE_REGISTRY": "0x094d12e5b541784701FD8d65F11fc0598FBC6332",

    # Balancer
    "BALANCER_VAULT": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
    "BALANCER_HELPERS": "0x239e55F427D44C3cc793f49bFB507ebe76638a2b",

    # Kyber Network
    "KYBER_ROUTER": "0x546C79662E028B661dFB4767664d0273184E4dD1",

    # DODO
    "DODO_PROXY": "0xa222f27c40cA5B9f138131eC6659582FdE16D2D7",
}

# =============================================================================
# CHAINLINK PRICE FEED ADDRESSES
# =============================================================================

CHAINLINK_FEEDS = {
    "ETH_USD": "0xF9680D99D6C9589e2a93a78A04A279e509205945",
    "MATIC_USD": "0xAB594600376Ec9fD91F8e885dADF0CE036862dE0",
    "BTC_USD": "0xc907E116054Ad103354f2D350FD2514433D57F6f",
    "LINK_USD": "0xd9FFdb71EbE7496cC440152d43986Aae0AB76665",
    "AAVE_USD": "0x72484B12719E23115761D5DA1646945632979bB6",
    "USDC_USD": "0xfE4A8cc5b5B2366C1B58Bea3858e81843581b2F7",
    "USDT_USD": "0x0A6513e40db6EB1b165753AD52E80663aeA50545",
}

# =============================================================================
# UTILITY ADDRESSES
# =============================================================================

UTILITY_ADDRESSES = {
    "MULTICALL3": "0xca11bde05977b3631167028862be2a173976ca11",
    "PERMIT2": "0x000000000022D473030F116dDEE9F6B43aC78BA3",
    "WETH9": POLYGON_ADDRESSES["WETH"],  # Alias for consistency
    "NATIVE_TOKEN": "0x0000000000000000000000000000000000000000",  # MATIC
}

# =============================================================================
# TOKEN METADATA
# =============================================================================

TOKEN_DECIMALS = {
    POLYGON_ADDRESSES["USDC"]: 6,
    POLYGON_ADDRESSES["USDT"]: 6,
    POLYGON_ADDRESSES["DAI"]: 18,
    POLYGON_ADDRESSES["WMATIC"]: 18,
    POLYGON_ADDRESSES["WETH"]: 18,
    POLYGON_ADDRESSES["WBTC"]: 8,
    POLYGON_ADDRESSES["LINK"]: 18,
    POLYGON_ADDRESSES["AAVE"]: 18,
    POLYGON_ADDRESSES["CRV"]: 18,
    POLYGON_ADDRESSES["SUSHI"]: 18,
    POLYGON_ADDRESSES["QUICK"]: 18,
    POLYGON_ADDRESSES["GHST"]: 18,
}

TOKEN_SYMBOLS = {
    POLYGON_ADDRESSES["USDC"]: "USDC",
    POLYGON_ADDRESSES["USDT"]: "USDT",
    POLYGON_ADDRESSES["DAI"]: "DAI",
    POLYGON_ADDRESSES["WMATIC"]: "WMATIC",
    POLYGON_ADDRESSES["WETH"]: "WETH",
    POLYGON_ADDRESSES["WBTC"]: "WBTC",
    POLYGON_ADDRESSES["LINK"]: "LINK",
    POLYGON_ADDRESSES["AAVE"]: "AAVE",
    POLYGON_ADDRESSES["CRV"]: "CRV",
    POLYGON_ADDRESSES["SUSHI"]: "SUSHI",
    POLYGON_ADDRESSES["QUICK"]: "QUICK",
    POLYGON_ADDRESSES["GHST"]: "GHST",
}

# =============================================================================
# TRADING PAIRS CONFIGURATION
# =============================================================================

PRIORITY_TRADING_PAIRS = [
    {
        "name": "USDC/WETH",
        "token_a": POLYGON_ADDRESSES["USDC"],
        "token_b": POLYGON_ADDRESSES["WETH"],
        "decimals_a": 6,
        "decimals_b": 18,
        "min_liquidity_usd": 100000,  # $100k minimum liquidity
        "expected_volume_24h": 1000000,  # $1M daily volume
        "priority": 1  # Highest priority
    },
    {
        "name": "USDC/WMATIC",
        "token_a": POLYGON_ADDRESSES["USDC"],
        "token_b": POLYGON_ADDRESSES["WMATIC"],
        "decimals_a": 6,
        "decimals_b": 18,
        "min_liquidity_usd": 50000,
        "expected_volume_24h": 500000,
        "priority": 2
    },
    {
        "name": "WETH/WMATIC",
        "token_a": POLYGON_ADDRESSES["WETH"],
        "token_b": POLYGON_ADDRESSES["WMATIC"],
        "decimals_a": 18,
        "decimals_b": 18,
        "min_liquidity_usd": 75000,
        "expected_volume_24h": 750000,
        "priority": 3
    },
    {
        "name": "USDC/USDT",
        "token_a": POLYGON_ADDRESSES["USDC"],
        "token_b": POLYGON_ADDRESSES["USDT"],
        "decimals_a": 6,
        "decimals_b": 6,
        "min_liquidity_usd": 200000,  # High liquidity needed for stablecoin arb
        "expected_volume_24h": 2000000,
        "priority": 4
    },
    {
        "name": "USDC/DAI",
        "token_a": POLYGON_ADDRESSES["USDC"],
        "token_b": POLYGON_ADDRESSES["DAI"],
        "decimals_a": 6,
        "decimals_b": 18,
        "min_liquidity_usd": 150000,
        "expected_volume_24h": 800000,
        "priority": 5
    },
    {
        "name": "WETH/WBTC",
        "token_a": POLYGON_ADDRESSES["WETH"],
        "token_b": POLYGON_ADDRESSES["WBTC"],
        "decimals_a": 18,
        "decimals_b": 8,
        "min_liquidity_usd": 100000,
        "expected_volume_24h": 600000,
        "priority": 6
    },
]

# Secondary pairs for scaling up
SECONDARY_TRADING_PAIRS = [
    {
        "name": "WMATIC/LINK",
        "token_a": POLYGON_ADDRESSES["WMATIC"],
        "token_b": POLYGON_ADDRESSES["LINK"],
        "decimals_a": 18,
        "decimals_b": 18,
        "min_liquidity_usd": 25000,
        "priority": 7
    },
    {
        "name": "USDC/AAVE",
        "token_a": POLYGON_ADDRESSES["USDC"],
        "token_b": POLYGON_ADDRESSES["AAVE"],
        "decimals_a": 6,
        "decimals_b": 18,
        "min_liquidity_usd": 30000,
        "priority": 8
    },
]

# =============================================================================
# DEX CONFIGURATION
# =============================================================================

DEX_CONFIG = {
    "quickswap": {
        "name": "QuickSwap",
        "router": DEX_ADDRESSES["QUICKSWAP_ROUTER"],
        "factory": DEX_ADDRESSES["QUICKSWAP_FACTORY"],
        "fee": 0.003,  # 0.3%
        "type": "uniswap_v2",
        "priority": 1,  # Primary DEX
        "gas_estimate": 150000
    },
    "sushiswap": {
        "name": "SushiSwap",
        "router": DEX_ADDRESSES["SUSHISWAP_ROUTER"],
        "factory": DEX_ADDRESSES["SUSHISWAP_FACTORY"],
        "fee": 0.003,  # 0.3%
        "type": "uniswap_v2",
        "priority": 2,
        "gas_estimate": 155000
    },
    "uniswap_v3": {
        "name": "Uniswap V3",
        "router": DEX_ADDRESSES["UNISWAP_V3_ROUTER"],
        "factory": DEX_ADDRESSES["UNISWAP_V3_FACTORY"],
        "quoter": DEX_ADDRESSES["UNISWAP_V3_QUOTER"],
        "fee_tiers": [0.0005, 0.003, 0.01],  # 0.05%, 0.3%, 1%
        "type": "uniswap_v3",
        "priority": 3,
        "gas_estimate": 180000
    },
    "one_inch": {
        "name": "1inch",
        "router": DEX_ADDRESSES["ONE_INCH_ROUTER"],
        "oracle": DEX_ADDRESSES["ONE_INCH_ORACLE"],
        "type": "aggregator",
        "priority": 4,  # Use for complex routes
        "gas_estimate": 200000
    }
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_token_symbol(address: str) -> str:
    """Get token symbol from address"""
    address_lower = address.lower()
    return TOKEN_SYMBOLS.get(address_lower, f"UNKNOWN({address[:6]}...)")


def get_token_decimals(address: str) -> int:
    """Get token decimals from address"""
    address_lower = address.lower()
    return TOKEN_DECIMALS.get(address_lower, 18)  # Default to 18 decimals


def validate_token_address(address: str) -> bool:
    """Validate if an address is a known token"""
    if not address or len(address) != 42 or not address.startswith('0x'):
        return False

    known_tokens = list(POLYGON_ADDRESSES.values())
    return address.lower() in [token.lower() for token in known_tokens]


def get_trading_pair_info(token_a: str, token_b: str) -> Optional[Dict]:
    """Get trading pair information"""
    all_pairs = PRIORITY_TRADING_PAIRS + SECONDARY_TRADING_PAIRS

    for pair in all_pairs:
        if ((pair["token_a"].lower() == token_a.lower() and
             pair["token_b"].lower() == token_b.lower()) or
                (pair["token_a"].lower() == token_b.lower() and
                 pair["token_b"].lower() == token_a.lower())):
            return pair

    return None


def get_dex_info(dex_name: str) -> Optional[Dict]:
    """Get DEX configuration information"""
    return DEX_CONFIG.get(dex_name.lower())


def get_all_token_addresses() -> List[str]:
    """Get list of all known token addresses"""
    return list(POLYGON_ADDRESSES.values())


def get_priority_pairs_by_priority() -> List[Dict]:
    """Get trading pairs sorted by priority"""
    return sorted(PRIORITY_TRADING_PAIRS, key=lambda x: x.get("priority", 999))


def format_address(address: str) -> str:
    """Format address to proper checksum format"""
    if not address:
        return ""

    # Basic checksum formatting (Web3.py does this better)
    return address.lower()


def get_stablecoin_addresses() -> List[str]:
    """Get list of stablecoin addresses"""
    return [
        POLYGON_ADDRESSES["USDC"],
        POLYGON_ADDRESSES["USDT"],
        POLYGON_ADDRESSES["DAI"]
    ]


def is_stablecoin(address: str) -> bool:
    """Check if token is a stablecoin"""
    return address.lower() in [addr.lower() for addr in get_stablecoin_addresses()]


def get_major_token_addresses() -> List[str]:
    """Get major tokens suitable for large flashloans"""
    return [
        POLYGON_ADDRESSES["USDC"],
        POLYGON_ADDRESSES["USDT"],
        POLYGON_ADDRESSES["WETH"],
        POLYGON_ADDRESSES["WMATIC"],
        POLYGON_ADDRESSES["DAI"],
        POLYGON_ADDRESSES["WBTC"]
    ]


def estimate_gas_for_dex(dex_name: str) -> int:
    """Estimate gas usage for DEX operations"""
    dex_info = get_dex_info(dex_name)
    if dex_info:
        return dex_info.get("gas_estimate", 150000)
    return 150000  # Default estimate


# =============================================================================
# CONSTANTS FOR CALCULATIONS
# =============================================================================

# Flashloan fee for Aave V3 (0.05%)
AAVE_FLASHLOAN_FEE_BPS = 5  # 5 basis points = 0.05%

# Typical DEX fees
UNISWAP_V2_FEE_BPS = 30  # 0.3%
UNISWAP_V3_LOW_FEE_BPS = 5  # 0.05%
UNISWAP_V3_MID_FEE_BPS = 30  # 0.3%
UNISWAP_V3_HIGH_FEE_BPS = 100  # 1%

# Gas estimates for different operations
GAS_ESTIMATES = {
    "ERC20_TRANSFER": 21000,
    "ERC20_APPROVE": 46000,
    "UNISWAP_V2_SWAP": 150000,
    "UNISWAP_V3_SWAP": 180000,
    "FLASHLOAN_EXECUTION": 350000,
    "ARBITRAGE_COMPLETE": 500000
}

# =============================================================================
# MUMBAI TESTNET ADDRESSES (for testing)
# =============================================================================

MUMBAI_ADDRESSES = {
    "USDC": "0xe6b8a5CF854791412c1f6EFC7CAf629f5Df1c747",
    "WETH": "0xA6FA4fB5f76172d178d61B04b0ecd319C5d1C0aa",
    "WMATIC": "0x9c3C9283D3e44854697Cd22D3Faa240Cfb032889",
    "AAVE_POOL": "0x6C9fB0D5bD9429eb9Cd96B85B81d872281771E6B",
    "AAVE_PROVIDER": "0x5343b5bA672Ae99d627A1C87866b8E53F47Db2E6",
}


def get_addresses_for_network(network: str = "polygon") -> Dict:
    """Get addresses for specified network"""
    if network.lower() in ["mumbai", "testnet"]:
        return MUMBAI_ADDRESSES
    return POLYGON_ADDRESSES


# =============================================================================
# EXPORT ALL ADDRESSES FOR EASY ACCESS
# =============================================================================

ALL_ADDRESSES = {
    **POLYGON_ADDRESSES,
    **AAVE_ADDRESSES,
    **DEX_ADDRESSES,
    **CHAINLINK_FEEDS,
    **UTILITY_ADDRESSES
}

# Create reverse lookup for quick symbol-to-address mapping
SYMBOL_TO_ADDRESS = {symbol: address for address, symbol in TOKEN_SYMBOLS.items()}

# Export commonly used address collections
FLASHLOAN_TOKENS = get_major_token_addresses()
STABLECOINS = get_stablecoin_addresses()
TRADING_PAIRS = get_priority_pairs_by_priority()
DEX_ROUTERS = [config["router"] for config in DEX_CONFIG.values() if "router" in config]
# Contract addresses
