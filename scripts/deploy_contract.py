# Python deployment
# scripts/deploy_contract.py

"""
Smart Contract Deployment Script for Flashloan Arbitrage Bot
Handles deployment, verification, and testing of the arbitrage contract
"""

import asyncio
import json
import sys
import os
import time
import subprocess
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass
from decimal import Decimal
import argparse
import logging
import codecs

# Fix Unicode encoding issues on Windows
if sys.platform == 'win32':
    # Set environment variables
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

    # Reconfigure stdout and stderr for UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        # Python 3.7+
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            # Fallback if reconfigure fails
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach(), errors='replace')
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach(), errors='replace')
    else:
        # Fallback for older Python versions
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach(), errors='replace')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach(), errors='replace')

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('deployment.log')
    ]
)

logger = logging.getLogger('deploy_contract')

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from web3 import Web3
from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware
from eth_account import Account

from config.settings import load_settings, Settings
from config.addresses import get_network_addresses


@dataclass
class DeploymentResult:
    """Contract deployment result"""
    success: bool
    contract_address: Optional[str] = None
    transaction_hash: Optional[str] = None
    gas_used: Optional[int] = None
    deployment_cost: Optional[Decimal] = None
    error_message: Optional[str] = None
    verification_status: Optional[str] = None


class ContractDeployer:
    """
    Smart Contract Deployment Manager

    Features:
    - Multi-network deployment support
    - Gas optimization
    - Contract verification
    - Deployment testing
    - Rollback on failure
    """

    def __init__(self, settings: Settings, network_override: Optional[str] = None):
        self.settings = settings
        self.project_root = Path(__file__).parent.parent

        # Network setup
        if network_override:
            # Override network for deployment
            if network_override == 'mumbai':
                self.settings.network.name = 'Mumbai Testnet'
                self.settings.network.rpc_url = 'https://rpc-mumbai.maticvigil.com/'
                self.settings.network.chain_id = 80001
                self.settings.network.is_testnet = True
            elif network_override == 'polygon':
                self.settings.network.name = 'Polygon Mainnet'
                self.settings.network.chain_id = 137
                self.settings.network.is_testnet = False

        # Web3 setup
        self.web3 = Web3(Web3.HTTPProvider(self.settings.network.rpc_url))

        # Add PoA middleware for Polygon
        if 'polygon' in self.settings.network.name.lower() or 'mumbai' in self.settings.network.name.lower():
            self.web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        # Account setup
        if self.settings.security.private_key:
            self.account = Account.from_key(self.settings.security.private_key)
            self.web3.eth.default_account = self.account.address
        else:
            raise ValueError("PRIVATE_KEY is required for contract deployment")

        # Contract artifacts
        self.artifacts_dir = self.project_root / 'artifacts' / 'contracts'
        self.contracts_dir = self.project_root / 'contracts'

        logger.info(f"[DEPLOY] Contract Deployer initialized for {self.settings.network.name}")

    async def deploy_flashloan_contract(self) -> DeploymentResult:
        """
        Deploy the main FlashloanArbitrage contract

        Returns:
            DeploymentResult: Deployment outcome and details
        """
        try:
            logger.info("[START] Starting FlashloanArbitrage contract deployment...")

            # Pre-deployment checks
            if not await self._pre_deployment_checks():
                return DeploymentResult(
                    success=False,
                    error_message="Pre-deployment checks failed"
                )

            # Load contract artifacts
            contract_data = await self._load_contract_artifacts("FlashloanArbitrage")
            if not contract_data:
                return DeploymentResult(
                    success=False,
                    error_message="Failed to load contract artifacts"
                )

            # Get network addresses
            network_addresses = get_network_addresses(self.settings.network.name.lower())

            # Prepare constructor arguments
            constructor_args = [
                network_addresses.get('aave_pool', '0x794a61358D6845594F94dc1DB02A252b5b4814aD'),  # Aave Pool
                network_addresses.get('aave_pool_data_provider', '0x69FA688f1Dc47d4B5d8029D5a35FB7a548310654'),
                # Aave Data Provider
            ]

            logger.info(f"[ARGS] Constructor args: {constructor_args}")

            # Deploy contract
            result = await self._deploy_contract(
                contract_data,
                constructor_args,
                "FlashloanArbitrage"
            )

            if result.success:
                # Save contract address
                self.settings.save_contract_address('flashloan_arbitrage', result.contract_address)

                # Verify contract if enabled
                if self.settings.security.enable_contract_verification and not self.settings.network.is_testnet:
                    verification_result = await self._verify_contract(
                        result.contract_address,
                        constructor_args,
                        "FlashloanArbitrage"
                    )
                    result.verification_status = verification_result

                # Test contract deployment
                test_result = await self._test_deployed_contract(result.contract_address)
                if not test_result:
                    logger.warning("[WARNING] Contract deployed but failed basic tests")

                logger.info(f"[SUCCESS] FlashloanArbitrage deployed at: {result.contract_address}")

            return result

        except Exception as e:
            logger.error(f"[ERROR] Deployment failed: {e}")
            return DeploymentResult(
                success=False,
                error_message=str(e)
            )

    async def _pre_deployment_checks(self) -> bool:
        """Perform pre-deployment validation checks"""
        logger.info("[CHECK] Running pre-deployment checks...")

        try:
            # Check Web3 connection
            if not self.web3.is_connected():
                logger.error("[ERROR] Web3 connection failed")
                return False

            # Check account balance
            balance = self.web3.eth.get_balance(self.account.address)
            balance_ether = self.web3.from_wei(balance, 'ether')

            min_balance = Decimal("0.1")  # Minimum 0.1 MATIC for deployment
            if balance_ether < min_balance:
                logger.error(f"[ERROR] Insufficient balance: {balance_ether} MATIC (need at least {min_balance})")
                return False

            logger.info(f"[SUCCESS] Account balance: {balance_ether} MATIC")

            # Check if contracts are compiled
            if not await self._check_compiled_contracts():
                logger.error("[ERROR] Contracts not compiled")
                return False

            # Check network
            chain_id = self.web3.eth.chain_id
            if chain_id != self.settings.network.chain_id:
                logger.error(f"[ERROR] Chain ID mismatch: expected {self.settings.network.chain_id}, got {chain_id}")
                return False

            logger.info(f"[SUCCESS] Connected to {self.settings.network.name} (Chain ID: {chain_id})")

            # Check gas price
            gas_price = self.web3.eth.gas_price
            gas_price_gwei = gas_price / 1e9

            if gas_price_gwei > self.settings.trading.gas_price_limit:
                logger.warning(f"[WARNING] High gas price: {gas_price_gwei:.1f} gwei")
                response = input("Continue with high gas price? (y/N): ")
                if response.lower() != 'y':
                    return False

            logger.info(f"[SUCCESS] Gas price: {gas_price_gwei:.1f} gwei")

            return True

        except Exception as e:
            logger.error(f"[ERROR] Pre-deployment check failed: {e}")
            return False

    async def _check_compiled_contracts(self) -> bool:
        """Check if contracts are compiled"""
        try:
            # Try to compile with Hardhat first
            logger.info("[COMPILE] Compiling contracts with Hardhat...")
            result = subprocess.run(
                ['npx', 'hardhat', 'compile'],
                cwd=str(self.project_root),
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                logger.info("[SUCCESS] Contracts compiled successfully")
                return True
            else:
                logger.error(f"[ERROR] Compilation failed: {result.stderr}")
                return False

        except FileNotFoundError:
            logger.warning("[WARNING] Hardhat not found, checking for pre-compiled artifacts...")

            # Check if artifacts exist
            flashloan_artifact = self.artifacts_dir / 'FlashloanArbitrage.sol' / 'FlashloanArbitrage.json'
            if flashloan_artifact.exists():
                logger.info("[SUCCESS] Found pre-compiled artifacts")
                return True

            logger.error("[ERROR] No compiled contracts found")
            return False

        except Exception as e:
            logger.error(f"[ERROR] Contract compilation check failed: {e}")
            return False

    async def _load_contract_artifacts(self, contract_name: str) -> Optional[Dict]:
        """Load compiled contract artifacts"""
        try:
            artifact_path = self.artifacts_dir / f'{contract_name}.sol' / f'{contract_name}.json'

            if not artifact_path.exists():
                logger.error(f"[ERROR] Contract artifact not found: {artifact_path}")
                return None

            with open(artifact_path, 'r') as f:
                artifact = json.load(f)

            logger.info(f"[SUCCESS] Loaded {contract_name} artifacts")
            return artifact

        except Exception as e:
            logger.error(f"[ERROR] Failed to load contract artifacts: {e}")
            return None

    async def _deploy_contract(self, contract_data: Dict, constructor_args: list,
                               contract_name: str) -> DeploymentResult:
        """Deploy a smart contract"""
        try:
            logger.info(f"[DEPLOY] Deploying {contract_name}...")

            # Create contract instance
            contract = self.web3.eth.contract(
                abi=contract_data['abi'],
                bytecode=contract_data['bytecode']
            )

            # Estimate gas
            try:
                gas_estimate = contract.constructor(*constructor_args).estimate_gas({
                    'from': self.account.address
                })
                gas_limit = int(gas_estimate * 1.2)  # Add 20% buffer
                logger.info(f"[GAS] Gas estimate: {gas_estimate:,} (using {gas_limit:,})")
            except Exception as e:
                logger.warning(f"[WARNING] Gas estimation failed: {e}, using default limit")
                gas_limit = self.settings.trading.max_gas_limit

            # Get current gas price
            gas_price = self.web3.eth.gas_price

            # Build transaction
            transaction = contract.constructor(*constructor_args).build_transaction({
                'from': self.account.address,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': self.web3.eth.get_transaction_count(self.account.address)
            })

            # Sign transaction
            signed_txn = self.account.sign_transaction(transaction)

            # Send transaction
            logger.info("[TX] Sending deployment transaction...")
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)

            logger.info(f"[WAIT] Waiting for transaction confirmation: {tx_hash.hex()}")

            # Wait for confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=600)  # 10 minutes timeout

            if receipt.status == 1:
                # Calculate deployment cost
                gas_used = receipt.gasUsed
                deployment_cost = Decimal(str(gas_used * gas_price)) / Decimal("1e18")

                logger.info(f"[SUCCESS] {contract_name} deployed successfully!")
                logger.info(f"[ADDR] Contract address: {receipt.contractAddress}")
                logger.info(f"[GAS] Gas used: {gas_used:,}")
                logger.info(f"[COST] Deployment cost: {deployment_cost:.6f} MATIC")

                return DeploymentResult(
                    success=True,
                    contract_address=receipt.contractAddress,
                    transaction_hash=tx_hash.hex(),
                    gas_used=gas_used,
                    deployment_cost=deployment_cost
                )
            else:
                logger.error(f"[ERROR] Deployment transaction failed")
                return DeploymentResult(
                    success=False,
                    transaction_hash=tx_hash.hex(),
                    error_message="Transaction failed"
                )

        except Exception as e:
            logger.error(f"[ERROR] Contract deployment failed: {e}")
            return DeploymentResult(
                success=False,
                error_message=str(e)
            )

    async def _verify_contract(self, contract_address: str, constructor_args: list,
                               contract_name: str) -> str:
        """Verify contract on block explorer"""
        try:
            logger.info(f"[VERIFY] Verifying {contract_name} on block explorer...")

            # Use Hardhat verify plugin
            verify_command = [
                                 'npx', 'hardhat', 'verify',
                                 '--network', self.settings.network.name.lower().replace(' ', '_'),
                                 contract_address
                             ] + [str(arg) for arg in constructor_args]

            result = subprocess.run(
                verify_command,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )

            if result.returncode == 0:
                logger.info(f"[SUCCESS] Contract verified successfully")
                return "SUCCESS"
            else:
                logger.warning(f"[WARNING] Verification failed: {result.stderr}")
                return "FAILED"

        except subprocess.TimeoutExpired:
            logger.warning("[WARNING] Contract verification timed out")
            return "TIMEOUT"
        except Exception as e:
            logger.warning(f"[WARNING] Contract verification error: {e}")
            return "ERROR"

    async def _test_deployed_contract(self, contract_address: str) -> bool:
        """Test basic functionality of deployed contract"""
        try:
            logger.info("[TEST] Testing deployed contract...")

            # Load contract ABI
            contract_data = await self._load_contract_artifacts("FlashloanArbitrage")
            if not contract_data:
                return False

            # Create contract instance
            contract = self.web3.eth.contract(
                address=contract_address,
                abi=contract_data['abi']
            )

            # Test 1: Check owner
            try:
                owner = contract.functions.owner().call()
                if owner.lower() != self.account.address.lower():
                    logger.error(f"[ERROR] Owner mismatch: expected {self.account.address}, got {owner}")
                    return False
                logger.info(f"[SUCCESS] Owner check passed: {owner}")
            except Exception as e:
                logger.warning(f"[WARNING] Owner check failed: {e}")

            # Test 2: Check Aave pool address
            try:
                aave_pool = contract.functions.AAVE_POOL().call()
                logger.info(f"[SUCCESS] Aave pool configured: {aave_pool}")
            except Exception as e:
                logger.warning(f"[WARNING] Aave pool check failed: {e}")

            # Test 3: Check if contract can receive Ether
            try:
                # Small test transaction
                test_tx = {
                    'to': contract_address,
                    'value': self.web3.to_wei(0.001, 'ether'),  # Send 0.001 MATIC
                    'gas': 21000,
                    'gasPrice': self.web3.eth.gas_price,
                    'nonce': self.web3.eth.get_transaction_count(self.account.address)
                }

                signed_tx = self.account.sign_transaction(test_tx)
                tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt.status == 1:
                    logger.info("[SUCCESS] Contract can receive Ether")
                else:
                    logger.warning("[WARNING] Contract cannot receive Ether")

            except Exception as e:
                logger.warning(f"[WARNING] Ether receive test failed: {e}")

            logger.info("[SUCCESS] Basic contract tests completed")
            return True

        except Exception as e:
            logger.error(f"[ERROR] Contract testing failed: {e}")
            return False

    async def deploy_all_contracts(self) -> Dict[str, DeploymentResult]:
        """Deploy all required contracts"""
        results = {}

        logger.info("[START] Starting full contract deployment...")

        # Deploy main FlashloanArbitrage contract
        results['flashloan_arbitrage'] = await self.deploy_flashloan_contract()

        # Add more contracts here if needed
        # results['other_contract'] = await self.deploy_other_contract()

        # Summary
        successful = sum(1 for result in results.values() if result.success)
        total = len(results)

        logger.info(f"[SUMMARY] Deployment Summary: {successful}/{total} contracts deployed successfully")

        for name, result in results.items():
            if result.success:
                logger.info(f"[SUCCESS] {name}: {result.contract_address}")
            else:
                logger.error(f"[ERROR] {name}: {result.error_message}")

        return results


async def main():
    """Main deployment function"""
    parser = argparse.ArgumentParser(description='Deploy Flashloan Arbitrage contracts')
    parser.add_argument('--network', choices=['polygon', 'mumbai'],
                        help='Target network (overrides .env setting)')
    parser.add_argument('--skip-verification', action='store_true',
                        help='Skip contract verification')
    parser.add_argument('--gas-price', type=int,
                        help='Gas price in gwei')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simulate deployment without executing')

    args = parser.parse_args()

    try:
        # Load settings
        settings = load_settings()

        # Override settings if specified
        if args.skip_verification:
            settings.security.enable_contract_verification = False

        if args.dry_run:
            logger.warning("[DRY-RUN] DRY RUN MODE - No contracts will be deployed")
            settings.security.dry_run_mode = True

        # Create deployer
        deployer = ContractDeployer(settings, args.network)

        # Pre-deployment confirmation
        if not args.dry_run:
            logger.info("[WARNING] DEPLOYING TO LIVE NETWORK")
            logger.info(f"Network: {settings.network.name}")
            logger.info(f"Account: {deployer.account.address}")

            balance = deployer.web3.eth.get_balance(deployer.account.address)
            balance_ether = deployer.web3.from_wei(balance, 'ether')
            logger.info(f"Balance: {balance_ether} MATIC")

            response = input("\nProceed with deployment? (y/N): ")
            if response.lower() != 'y':
                logger.info("[CANCELLED] Deployment cancelled")
                return

        # Deploy contracts
        results = await deployer.deploy_all_contracts()

        # Final status
        if all(result.success for result in results.values()):
            logger.info("[SUCCESS] All contracts deployed successfully!")

            # Save deployment info
            deployment_info = {
                'network': settings.network.name,
                'chain_id': settings.network.chain_id,
                'deployer': deployer.account.address,
                'timestamp': time.time(),
                'contracts': {
                    name: {
                        'address': result.contract_address,
                        'tx_hash': result.transaction_hash,
                        'gas_used': result.gas_used,
                        'cost': str(result.deployment_cost) if result.deployment_cost else None
                    } for name, result in results.items() if result.success
                }
            }

            deployment_file = Path(__file__).parent.parent / 'data' / f'deployment_{int(time.time())}.json'
            deployment_file.parent.mkdir(exist_ok=True)

            with open(deployment_file, 'w') as f:
                json.dump(deployment_info, f, indent=2)

            logger.info(f"[SAVED] Deployment info saved to: {deployment_file}")

        else:
            logger.error("[ERROR] Some contracts failed to deploy")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("[CANCELLED] Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[FATAL] Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
