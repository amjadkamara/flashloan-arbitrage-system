# Python deployment
# scripts/deploy_contract.py

# scripts/deploy_contract.py
"""
Smart Contract Deployment Script for Flashloan Arbitrage Bot
Fixed version that works with your actual project structure
"""

import json
import sys
import os
import time
from pathlib import Path
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

# Setup paths
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Load environment variables
load_dotenv(project_root / 'config' / '.env')


def load_contract_artifact(contract_name):
    """Load compiled contract artifacts"""
    artifact_path = project_root / 'artifacts' / 'contracts' / f'{contract_name}.sol' / f'{contract_name}.json'

    if not artifact_path.exists():
        print(f"Contract artifact not found: {artifact_path}")
        return None

    with open(artifact_path, 'r') as f:
        return json.load(f)


def deploy_contract():
    """Deploy FlashloanArbitrage contract"""
    print("Starting FlashloanArbitrage contract deployment...")

    # Setup Web3 connection
    rpc_url = os.getenv('WEB3_PROVIDER_URL')
    if not rpc_url:
        print("WEB3_PROVIDER_URL not set in .env file")
        return False

    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        print("Failed to connect to Web3 provider")
        return False

    print(f"Connected to network (Chain ID: {w3.eth.chain_id})")

    # Setup account
    private_key = os.getenv('PRIVATE_KEY')
    if not private_key:
        print("PRIVATE_KEY not set in .env file")
        return False

    account = Account.from_key(private_key)

    # Check balance
    balance = w3.eth.get_balance(account.address)
    balance_matic = w3.from_wei(balance, 'ether')
    print(f"Account: {account.address}")
    print(f"Balance: {float(balance_matic):.4f} MATIC")

    if balance_matic < 0.5:
        print("Low balance - deployment may fail")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return False

    # Load contract artifacts
    contract_data = load_contract_artifact('FlashloanArbitrage')
    if not contract_data:
        return False

    print("Contract artifacts loaded")

    # Create contract instance
    contract = w3.eth.contract(
        abi=contract_data['abi'],
        bytecode=contract_data['bytecode']
    )

    # Polygon mainnet addresses for constructor
    aave_addresses_provider = "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"  # Aave Addresses Provider
    oneinch_router = "0x1111111254EEB25477B68fb85Ed929f73A960582"  # 1inch V5 Router
    wmatic = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"  # Wrapped MATIC
    initial_executor = account.address  # Use deployer as initial executor

    constructor_args = [aave_addresses_provider, oneinch_router, wmatic, initial_executor]
    print(f"Constructor args: {constructor_args}")

    try:
        # Estimate gas
        gas_estimate = contract.constructor(*constructor_args).estimate_gas({
            'from': account.address
        })
        gas_limit = int(gas_estimate * 1.2)  # Add 20% buffer
        print(f"Gas estimate: {gas_estimate:,} (using {gas_limit:,})")

        # Get gas price
        gas_price = w3.eth.gas_price
        gas_price_gwei = gas_price / 1e9
        print(f"Gas price: {gas_price_gwei:.1f} gwei")

        # Calculate cost
        estimated_cost = w3.from_wei(gas_limit * gas_price, 'ether')
        print(f"Estimated cost: {float(estimated_cost):.6f} MATIC")

        # Confirm deployment
        print("\nDEPLOYING TO POLYGON MAINNET")
        response = input("Proceed with deployment? (y/N): ")
        if response.lower() != 'y':
            print("Deployment cancelled")
            return False

        # Build transaction
        transaction = contract.constructor(*constructor_args).build_transaction({
            'from': account.address,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': w3.eth.get_transaction_count(account.address)
        })

        # Sign transaction (FIXED: proper attribute access)
        signed_txn = account.sign_transaction(transaction)
        print("Sending deployment transaction...")

        # Send transaction (FIXED: proper raw transaction access)
        if hasattr(signed_txn, 'rawTransaction'):
            raw_tx = signed_txn.rawTransaction
        elif hasattr(signed_txn, 'raw_transaction'):
            raw_tx = signed_txn.raw_transaction
        else:
            raw_tx = signed_txn['rawTransaction']

        tx_hash = w3.eth.send_raw_transaction(raw_tx)

        print(f"Transaction hash: {tx_hash.hex()}")
        print("Waiting for confirmation...")

        # Wait for receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=600)

        if receipt.status == 1:
            contract_address = receipt.contractAddress
            gas_used = receipt.gasUsed
            actual_cost = w3.from_wei(gas_used * gas_price, 'ether')

            print("\nDEPLOYMENT SUCCESSFUL!")
            print(f"Contract Address: {contract_address}")
            print(f"Transaction: {tx_hash.hex()}")
            print(f"Gas Used: {gas_used:,}")
            print(f"Actual Cost: {float(actual_cost):.6f} MATIC")

            # Update addresses.py file
            update_addresses_file(contract_address)

            # Save deployment info
            save_deployment_info(contract_address, tx_hash.hex(), gas_used, float(actual_cost))

            print(f"View on PolygonScan: https://polygonscan.com/address/{contract_address}")

            return True
        else:
            print("Deployment transaction failed")
            return False

    except Exception as e:
        print(f"Deployment failed: {e}")
        return False


def update_addresses_file(contract_address):
    """Update the addresses.py file with the new contract address"""
    try:
        addresses_file = project_root / 'config' / 'addresses.py'

        # Read current content
        with open(addresses_file, 'r') as f:
            content = f.read()

        # Add contract address at the end
        new_content = content + f"\n# Deployed contract address\nCONTRACT_ADDRESS = '{contract_address}'\n"

        # Write updated content
        with open(addresses_file, 'w') as f:
            f.write(new_content)

        print(f"Updated {addresses_file} with contract address")

    except Exception as e:
        print(f"Failed to update addresses.py: {e}")


def save_deployment_info(contract_address, tx_hash, gas_used, cost):
    """Save deployment information"""
    try:
        data_dir = project_root / 'data'
        data_dir.mkdir(exist_ok=True)

        deployment_info = {
            'contract_address': contract_address,
            'transaction_hash': tx_hash,
            'gas_used': gas_used,
            'cost_matic': cost,
            'timestamp': int(time.time()),
            'network': 'Polygon Mainnet',
            'chain_id': 137
        }

        filename = f'deployment_{int(time.time())}.json'
        filepath = data_dir / filename

        with open(filepath, 'w') as f:
            json.dump(deployment_info, f, indent=2)

        print(f"Deployment info saved to {filepath}")

    except Exception as e:
        print(f"Failed to save deployment info: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("FLASHLOAN ARBITRAGE BOT - CONTRACT DEPLOYMENT")
    print("=" * 60)

    success = deploy_contract()

    if success:
        print("\nDeployment completed successfully!")
        print("\nNext steps:")
        print("1. Test the deployment with: python -m bot.arbitrage_bot --dry-run")
        print("2. Start monitoring: python scripts/monitor_performance.py")
        print("3. Begin trading: python -m bot.arbitrage_bot")
    else:
        print("\nDeployment failed!")
        sys.exit(1)
