# Web3 contract interaction
# bot/contract_interface.py
"""
Contract Interface - Web3 Contract Interaction Layer

This module handles all interactions with the FlashloanArbitrage smart contract
and other DeFi protocols on the Polygon network. It provides a clean interface
for executing flashloan arbitrage trades and managing contract state.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from pathlib import Path

from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ContractLogicError, TransactionNotFound
from eth_account import Account
from eth_utils import to_checksum_address

from config.settings import Settings
from config.addresses import POLYGON_ADDRESSES
from .utils.helpers import format_amount, calculate_gas_price
from .utils.logger import setup_logger

# Setup logging
logger = setup_logger(__name__)


class ContractInterface:
    """
    Handles all smart contract interactions for the flashloan arbitrage bot.

    Features:
    - FlashloanArbitrage contract interaction
    - Gas price optimization
    - Transaction monitoring and confirmation
    - Error handling and retry logic
    - Multi-DEX swap execution
    - Profit calculation and validation
    """

    def __init__(self, settings: Settings):
        """Initialize the contract interface with Web3 connection and contracts."""
        self.settings = settings
        self.w3 = None
        self.account = None
        self.flashloan_contract = None
        self.contract_abi = {}

        # Transaction settings
        self.max_retries = 3
        self.confirmation_blocks = 2
        self.timeout_seconds = 300

        # Initialize Web3 connection
        self._setup_web3()
        self._setup_account()
        self._load_contracts()

        logger.info("ContractInterface initialized successfully")
        logger.info(f"Connected to network: {self.w3.net.version}")
        logger.info(f"Account address: {self.account.address}")

    def _setup_web3(self) -> None:
        """Setup Web3 connection to Polygon network."""
        try:
            self.w3 = Web3(Web3.HTTPProvider(self.settings.network.rpc_url))

            # Verify connection
            if not self.w3.is_connected():
                raise ConnectionError("Failed to connect to Polygon RPC")

            # Set default account for gas estimation
            self.w3.eth.default_account = self.w3.to_checksum_address(
                Account.from_key(self.settings.security.private_key).address
            )

            logger.info("Web3 connection established")

        except Exception as e:
            logger.error(f"Failed to setup Web3: {e}")
            raise

    def _setup_account(self) -> None:
        """Setup the trading account from private key."""
        try:
            self.account = Account.from_key(self.settings.security.private_key)
            logger.info(f"Account loaded: {self.account.address}")

            # Check account balance
            balance = self.w3.eth.get_balance(self.account.address)
            balance_matic = self.w3.from_wei(balance, 'ether')

            if balance_matic < 0.1:
                logger.warning(f"Low MATIC balance: {balance_matic:.4f} MATIC")
            else:
                logger.info(f"Account balance: {balance_matic:.4f} MATIC")

        except Exception as e:
            logger.error(f"Failed to setup account: {e}")
            raise

    def _load_contracts(self) -> None:
        """Load contract ABIs and create contract instances."""
        try:
            # Load FlashloanArbitrage contract
            contract_path = Path("contracts/artifacts/FlashloanArbitrage.json")
            if contract_path.exists():
                with open(contract_path, 'r') as f:
                    contract_artifact = json.load(f)

                self.contract_abi['FlashloanArbitrage'] = contract_artifact['abi']
                self.flashloan_contract = self.w3.eth.contract(
                    address=to_checksum_address(self.settings.CONTRACT_ADDRESS),
                    abi=self.contract_abi['FlashloanArbitrage']
                )

                logger.info(f"FlashloanArbitrage contract loaded: {self.settings.CONTRACT_ADDRESS}")
            else:
                logger.warning("FlashloanArbitrage contract artifact not found")

            # Load other contract ABIs (ERC20, etc.)
            self._load_standard_abis()

        except Exception as e:
            logger.error(f"Failed to load contracts: {e}")
            raise

    def _load_standard_abis(self) -> None:
        """Load standard contract ABIs (ERC20, etc.)."""
        # ERC20 ABI (basic functions we need)
        erc20_abi = [
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            }
        ]

        self.contract_abi['ERC20'] = erc20_abi
        logger.info("Standard contract ABIs loaded")

    def execute_arbitrage(
            self,
            asset: str,
            amount: int,
            dex_addresses: List[str],
            swap_data: List[bytes],
            min_profit: int
    ) -> Optional[str]:
        """
        Execute a flashloan arbitrage trade.

        Args:
            asset: Token address to borrow
            amount: Amount to borrow (in wei)
            dex_addresses: List of DEX router addresses for swaps
            swap_data: List of encoded swap data for each DEX
            min_profit: Minimum profit required (in wei)

        Returns:
            Transaction hash if successful, None if failed
        """
        try:
            logger.info(f"Executing arbitrage for {format_amount(amount, 18)} {asset[:8]}...")

            # Get current gas price
            gas_price = calculate_gas_price(self.w3, self.settings.MAX_GAS_PRICE_GWEI)

            # Build transaction
            txn = self.flashloan_contract.functions.executeArbitrage(
                asset,
                amount,
                dex_addresses,
                swap_data,
                min_profit
            ).build_transaction({
                'from': self.account.address,
                'gasPrice': gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
            })

            # Estimate gas
            try:
                gas_estimate = self.w3.eth.estimate_gas(txn)
                txn['gas'] = int(gas_estimate * 1.2)  # Add 20% buffer
                logger.info(f"Gas estimate: {gas_estimate:,}")
            except ContractLogicError as e:
                logger.error(f"Transaction would fail: {e}")
                return None

            # Calculate transaction cost
            tx_cost = txn['gas'] * txn['gasPrice']
            tx_cost_matic = self.w3.from_wei(tx_cost, 'ether')

            logger.info(f"Transaction cost: {tx_cost_matic:.6f} MATIC")

            # Check profitability after gas costs
            if not self._is_profitable_after_gas(min_profit, tx_cost):
                logger.warning("Trade not profitable after gas costs")
                return None

            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(txn, self.settings.security.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)

            logger.info(f"Transaction sent: {tx_hash.hex()}")

            # Wait for confirmation
            return self._wait_for_confirmation(tx_hash)

        except Exception as e:
            logger.error(f"Failed to execute arbitrage: {e}")
            return None

    def _is_profitable_after_gas(self, expected_profit: int, gas_cost: int) -> bool:
        """Check if trade remains profitable after gas costs."""
        net_profit = expected_profit - gas_cost
        profit_threshold = self.w3.to_wei(self.settings.MIN_PROFIT_PERCENTAGE / 100, 'ether')

        return net_profit > profit_threshold

    def _wait_for_confirmation(self, tx_hash: bytes, max_wait: int = 300) -> Optional[str]:
        """
        Wait for transaction confirmation.

        Args:
            tx_hash: Transaction hash to monitor
            max_wait: Maximum wait time in seconds

        Returns:
            Transaction hash if confirmed, None if failed/timeout
        """
        try:
            logger.info("Waiting for transaction confirmation...")

            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=max_wait,
                poll_latency=5
            )

            if receipt.status == 1:
                logger.info(f"Transaction confirmed in block {receipt.blockNumber}")
                logger.info(f"Gas used: {receipt.gasUsed:,}")

                # Parse logs for profit information
                self._parse_arbitrage_logs(receipt)

                return tx_hash.hex()
            else:
                logger.error("Transaction failed")
                return None

        except TransactionNotFound:
            logger.error("Transaction not found - may have been dropped")
            return None
        except Exception as e:
            logger.error(f"Error waiting for confirmation: {e}")
            return None

    def _parse_arbitrage_logs(self, receipt) -> None:
        """Parse transaction logs to extract arbitrage results."""
        try:
            # Decode logs using contract ABI
            logs = self.flashloan_contract.events.ArbitrageExecuted().process_receipt(receipt)

            for log in logs:
                args = log['args']
                asset = args['asset']
                amount = args['amount']
                profit = args['profit']

                logger.info(f"Arbitrage executed:")
                logger.info(f"  Asset: {asset}")
                logger.info(f"  Amount: {format_amount(amount, 18)}")
                logger.info(f"  Profit: {format_amount(profit, 18)} MATIC")

        except Exception as e:
            logger.warning(f"Could not parse arbitrage logs: {e}")

    def get_contract_balance(self, token_address: str) -> Decimal:
        """Get token balance of the arbitrage contract."""
        try:
            if token_address == "0x0000000000000000000000000000000000000000":
                # Native MATIC
                balance = self.w3.eth.get_balance(self.settings.CONTRACT_ADDRESS)
                return self.w3.from_wei(balance, 'ether')
            else:
                # ERC20 token
                token_contract = self.w3.eth.contract(
                    address=to_checksum_address(token_address),
                    abi=self.contract_abi['ERC20']
                )

                balance = token_contract.functions.balanceOf(
                    self.settings.CONTRACT_ADDRESS
                ).call()

                decimals = token_contract.functions.decimals().call()
                return Decimal(balance) / Decimal(10 ** decimals)

        except Exception as e:
            logger.error(f"Failed to get contract balance for {token_address}: {e}")
            return Decimal(0)

    def get_supported_tokens(self) -> List[Dict[str, Any]]:
        """Get list of supported tokens from the contract."""
        try:
            supported_tokens = []

            # Get supported tokens from contract
            token_count = self.flashloan_contract.functions.getSupportedTokenCount().call()

            for i in range(token_count):
                token_addr = self.flashloan_contract.functions.getSupportedToken(i).call()

                # Get token info
                token_contract = self.w3.eth.contract(
                    address=token_addr,
                    abi=self.contract_abi['ERC20']
                )

                try:
                    symbol = token_contract.functions.symbol().call()
                    decimals = token_contract.functions.decimals().call()

                    supported_tokens.append({
                        'address': token_addr,
                        'symbol': symbol,
                        'decimals': decimals
                    })
                except:
                    # Skip tokens we can't read
                    continue

            logger.info(f"Found {len(supported_tokens)} supported tokens")
            return supported_tokens

        except Exception as e:
            logger.error(f"Failed to get supported tokens: {e}")
            return []

    def pause_contract(self) -> bool:
        """Pause the arbitrage contract (owner only)."""
        try:
            txn = self.flashloan_contract.functions.pause().build_transaction({
                'from': self.account.address,
                'gasPrice': calculate_gas_price(self.w3, self.settings.MAX_GAS_PRICE_GWEI),
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
            })

            signed_txn = self.w3.eth.account.sign_transaction(txn, self.settings.security.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)

            result = self._wait_for_confirmation(tx_hash)
            if result:
                logger.info("Contract paused successfully")
                return True

        except Exception as e:
            logger.error(f"Failed to pause contract: {e}")

        return False

    def emergency_withdraw(self, token_address: str) -> bool:
        """Emergency withdraw tokens from contract (owner only)."""
        try:
            txn = self.flashloan_contract.functions.emergencyWithdraw(
                token_address
            ).build_transaction({
                'from': self.account.address,
                'gasPrice': calculate_gas_price(self.w3, self.settings.MAX_GAS_PRICE_GWEI),
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
            })

            signed_txn = self.w3.eth.account.sign_transaction(txn, self.settings.security.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)

            result = self._wait_for_confirmation(tx_hash)
            if result:
                logger.info(f"Emergency withdrawal successful for {token_address}")
                return True

        except Exception as e:
            logger.error(f"Failed to emergency withdraw: {e}")

        return False

    def get_network_info(self) -> Dict[str, Any]:
        """Get current network information."""
        try:
            latest_block = self.w3.eth.get_block('latest')
            gas_price = self.w3.eth.gas_price

            return {
                'network_id': self.w3.net.version,
                'latest_block': latest_block.number,
                'gas_price_gwei': self.w3.from_wei(gas_price, 'gwei'),
                'account_balance': self.w3.from_wei(
                    self.w3.eth.get_balance(self.account.address), 'ether'
                ),
                'is_connected': self.w3.is_connected()
            }

        except Exception as e:
            logger.error(f"Failed to get network info: {e}")
            return {}

    def __str__(self) -> str:
        """String representation of the contract interface."""
        return f"ContractInterface(network={self.w3.net.version}, account={self.account.address[:8]}...)"
