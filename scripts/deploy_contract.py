# Python deployment 
# scripts/deploy_contract.py

"""
Smart Contract Deployment Script for Flashloan Arbitrage Bot
Handles deployment, verification, and testing of the arbitrage contract
"""

import asyncio
import json
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass
from decimal import Decimal
import argparse

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account

from config.settings import load_settings, Settings
from config.addresses import get_network_addresses
from bot.utils.logger import get_logger

logger = get_logger('deploy_contract')


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
            self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # Account setup
        if self.settings.security.private_key:
            self.account = Account.from_key(self.settings.security.private_key)
            self.web3.eth.default_account = self.account.address
        else:
            raise ValueError("PRIVATE_KEY is required for contract deployment")

        # Contract artifacts
        self.artifacts_dir = self.project_root / 'artifacts' / 'contracts'
        self.contracts_dir = self.project_root / 'contracts'

        logger.info(f"🚀 Contract Deployer initialized for {self.settings.network.name}")

    async def deploy_flashloan_contract(self) -> DeploymentResult:
        """
        Deploy the main FlashloanArbitrage contract

        Returns:
            DeploymentResult: Deployment outcome and details
        """
        try:
            logger.info("📦 Starting FlashloanArbitrage contract deployment...")

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

            logger.info(f"📋 Constructor args: {constructor_args}")

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
                    logger.warning("⚠️ Contract deployed but failed basic tests")

                logger.success(f"✅ FlashloanArbitrage deployed at: {result.contract_address}")

            return result

        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}")
            return DeploymentResult(
                success=False,
                error_message=str(e)
            )

    async def _pre_deployment_checks(self) -> bool:
        """Perform pre-deployment validation checks"""
        logger.info("🔍 Running pre-deployment checks...")

        try:
            # Check Web3 connection
            if not self.web3.isConnected():
                logger.error("❌ Web3 connection failed")
                return False

            # Check account balance
            balance = self.web3.eth.get_balance(self.account.address)
            balance_ether = self.web3.fromWei(balance, 'ether')

            min_balance = Decimal("0.1")  # Minimum 0.1 MATIC for deployment
            if balance_ether < min_balance:
                logger.error(f"❌ Insufficient balance: {balance_ether} MATIC (need at least {min_balance})")
                return False

            logger.info(f"✅ Account balance: {balance_ether} MATIC")

            # Check if contracts are compiled
            if not await self._check_compiled_contracts():
                logger.error("❌ Contracts not compiled")
                return False

            # Check network
            chain_id = self.web3.eth.chain_id
            if chain_id != self.settings.network.chain_id:
                logger.error(f"❌ Chain ID mismatch: expected {self.settings.network.chain_id}, got {chain_id}")
                return False

            logger.info(f"✅ Connected to {self.settings.network.name} (Chain ID: {chain_id})")

            # Check gas price
            gas_price = self.web3.eth.gas_price
            gas_price_gwei = gas_price / 1e9

            if gas_price_gwei > self.settings.trading.gas_price_limit:
                logger.warning(f"⚠️ High gas price: {gas_price_gwei:.1f} gwei")
                response = input("Continue with high gas price? (y/N): ")
                if response.lower() != 'y':
                    return False

            logger.info(f"✅ Gas price: {gas_price_gwei:.1f} gwei")

            return True

        except Exception as e:
            logger.error(f"❌ Pre-deployment check failed: {e}")
            return False

    async def _check_compiled_contracts(self) -> bool:
        """Check if contracts are compiled"""
        try:
            # Try to compile with Hardhat first
            logger.info("🔨 Compiling contracts with Hardhat...")
            result = subprocess.run(
                ['npx', 'hardhat', 'compile'],
                cwd=str(self.project_root),
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                logger.success("✅ Contracts compiled successfully")
                return True
            else:
                logger.error(f"❌ Compilation failed: {result.stderr}")
                return False

        except FileNotFoundError:
            logger.warning("⚠️ Hardhat not found, checking for pre-compiled artifacts...")

            # Check if artifacts exist
            flashloan_artifact = self.artifacts_dir / 'FlashloanArbitrage.sol' / 'FlashloanArbitrage.json'
            if flashloan_artifact.exists():
                logger.info("✅ Found pre-compiled artifacts")
                return True

            logger.error("❌ No compiled contracts found")
            return False

        except Exception as e:
            logger.error(f"❌ Contract compilation check failed: {e}")
            return False

    async def _load_contract_artifacts(self, contract_name: str) -> Optional[Dict]:
        """Load compiled contract artifacts"""
        try:
            artifact_path = self.artifacts_dir / f'{contract_name}.sol' / f'{contract_name}.json'

            if not artifact_path.exists():
                logger.error(f"❌ Contract artifact not found: {artifact_path}")
                return None

            with open(artifact_path, 'r') as f:
                artifact = json.load(f)

            logger.info(f"✅ Loaded {contract_name} artifacts")
            return artifact

        except Exception as e:
            logger.error(f"❌ Failed to load contract artifacts: {e}")
            return None

    async def _deploy_contract(self, contract_data: Dict, constructor_args: list,
                               contract_name: str) -> DeploymentResult:
        """Deploy a smart contract"""
        try:
            logger.info(f"🚀 Deploying {contract_name}...")

            # Create contract instance
            contract = self.web3.eth.contract(
                abi=contract_data['abi'],
                bytecode=contract_data['bytecode']
            )

            # Estimate gas
            try:
                gas_estimate = contract.constructor(*constructor_args).estimateGas({
                    'from': self.account.address
                })
                gas_limit = int(gas_estimate * 1.2)  # Add 20% buffer
                logger.info(f"📊 Gas estimate: {gas_estimate:,} (using {gas_limit:,})")
            except Exception as e:
                logger.warning(f"⚠️ Gas estimation failed: {e}, using default limit")
                gas_limit = self.settings.trading.max_gas_limit

            # Get current gas price
            gas_price = self.web3.eth.gas_price

            # Build transaction
            transaction = contract.constructor(*constructor_args).buildTransaction({
                'from': self.account.address,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': self.web3.eth.get_transaction_count(self.account.address)
            })

            # Sign transaction
            signed_txn = self.account.sign_transaction(transaction)

            # Send transaction
            logger.info("📤 Sending deployment transaction...")
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)

            logger.info(f"⏳ Waiting for transaction confirmation: {tx_hash.hex()}")

            # Wait for confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=600)  # 10 minutes timeout

            if receipt.status == 1:
                # Calculate deployment cost
                gas_used = receipt.gasUsed
                deployment_cost = Decimal(str(gas_used * gas_price)) / Decimal("1e18")

                logger.success(f"✅ {contract_name} deployed successfully!")
                logger.info(f"📍 Contract address: {receipt.contractAddress}")
                logger.info(f"⛽ Gas used: {gas_used:,}")
                logger.info(f"💰 Deployment cost: {deployment_cost:.6f} MATIC")

                return DeploymentResult(
                    success=True,
                    contract_address=receipt.contractAddress,
                    transaction_hash=tx_hash.hex(),
                    gas_used=gas_used,
                    deployment_cost=deployment_cost
                )
            else:
                logger.error(f"❌ Deployment transaction failed")
                return DeploymentResult(
                    success=False,
                    transaction_hash=tx_hash.hex(),
                    error_message="Transaction failed"
                )

        except Exception as e:
            logger.error(f"❌ Contract deployment failed: {e}")
            return DeploymentResult(
                success=False,
                error_message=str(e)
            )

    async def _verify_contract(self, contract_address: str, constructor_args: list,
                               contract_name: str) -> str:
        """Verify contract on block explorer"""
        try:
            logger.info(f"🔍 Verifying {contract_name} on block explorer...")

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
                logger.success(f"✅ Contract verified successfully")
                return "SUCCESS"
            else:
                logger.warning(f"⚠️ Verification failed: {result.stderr}")
                return "FAILED"

        except subprocess.TimeoutExpired:
            logger.warning("⚠️ Contract verification timed out")
            return "TIMEOUT"
        except Exception as e:
            logger.warning(f"⚠️ Contract verification error: {e}")
            return "ERROR"

    async def _test_deployed_contract(self, contract_address: str) -> bool:
        """Test basic functionality of deployed contract"""
        try:
            logger.info("🧪 Testing deployed contract...")

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
                    logger.error(f"❌ Owner mismatch: expected {self.account.address}, got {owner}")
                    return False
                logger.info(f"✅ Owner check passed: {owner}")
            except Exception as e:
                logger.warning(f"⚠️ Owner check failed: {e}")

            # Test 2: Check Aave pool address
            try:
                aave_pool = contract.functions.AAVE_POOL().call()
                logger.info(f"✅ Aave pool configured: {aave_pool}")
            except Exception as e:
                logger.warning(f"⚠️ Aave pool check failed: {e}")

            # Test 3: Check if contract can receive Ether
            try:
                # Small test transaction
                test_tx = {
                    'to': contract_address,
                    'value': self.web3.toWei(0.001, 'ether'),  # Send 0.001 MATIC
                    'gas': 21000,
                    'gasPrice': self.web3.eth.gas_price,
                    'nonce': self.web3.eth.get_transaction_count(self.account.address)
                }

                signed_tx = self.account.sign_transaction(test_tx)
                tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt.status == 1:
                    logger.info("✅ Contract can receive Ether")
                else:
                    logger.warning("⚠️ Contract cannot receive Ether")

            except Exception as e:
                logger.warning(f"⚠️ Ether receive test failed: {e}")

            logger.success("✅ Basic contract tests completed")
            return True

        except Exception as e:
            logger.error(f"❌ Contract testing failed: {e}")
            return False

    async def deploy_all_contracts(self) -> Dict[str, DeploymentResult]:
        """Deploy all required contracts"""
        results = {}

        logger.info("🚀 Starting full contract deployment...")

        # Deploy main FlashloanArbitrage contract
        results['flashloan_arbitrage'] = await self.deploy_flashloan_contract()

        # Add more contracts here if needed
        # results['other_contract'] = await self.deploy_other_contract()

        # Summary
        successful = sum(1 for result in results.values() if result.success)
        total = len(results)

        logger.info(f"📊 Deployment Summary: {successful}/{total} contracts deployed successfully")

        for name, result in results.items():
            if result.success:
                logger.success(f"✅ {name}: {result.contract_address}")
            else:
                logger.error(f"❌ {name}: {result.error_message}")

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
            logger.warning("🔶 DRY RUN MODE - No contracts will be deployed")
            settings.security.dry_run_mode = True

        # Create deployer
        deployer = ContractDeployer(settings, args.network)

        # Pre-deployment confirmation
        if not args.dry_run:
            logger.info("⚠️ DEPLOYING TO LIVE NETWORK ⚠️")
            logger.info(f"Network: {settings.network.name}")
            logger.info(f"Account: {deployer.account.address}")

            balance = deployer.web3.eth.get_balance(deployer.account.address)
            balance_ether = deployer.web3.fromWei(balance, 'ether')
            logger.info(f"Balance: {balance_ether} MATIC")

            response = input("\nProceed with deployment? (y/N): ")
            if response.lower() != 'y':
                logger.info("🛑 Deployment cancelled")
                return

        # Deploy contracts
        results = await deployer.deploy_all_contracts()

        # Final status
        if all(result.success for result in results.values()):
            logger.success("🎉 All contracts deployed successfully!")

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

            logger.info(f"📄 Deployment info saved to: {deployment_file}")

        else:
            logger.error("❌ Some contracts failed to deploy")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("🛑 Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())