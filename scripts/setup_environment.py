# Initial setup 
# scripts/setup_environment.py

"""
Setup Environment Script
Automates the initial setup and configuration of the flashloan arbitrage bot
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.a# scripts/setup_environment_safe.py
"""
Windows-Safe Setup Environment Script
Automates the initial setup without unicode issues
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional

# Simple print-based logging to avoid import issues
def log_info(msg):
    print(f"[INFO] {msg}")

def log_success(msg):
    print(f"[SUCCESS] {msg}")

def log_warning(msg):
    print(f"[WARNING] {msg}")

def log_error(msg):
    print(f"[ERROR] {msg}")

class SafeEnvironmentSetup:
    """Handles automated environment setup without unicode issues"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_dir = self.project_root / 'config'
        self.contracts_dir = self.project_root / 'contracts'

    def run_setup(self) -> bool:
        """Run complete environment setup"""
        print("=" * 60)
        print("FLASHLOAN ARBITRAGE BOT - SAFE SETUP")
        print("=" * 60)

        try:
            # Setup steps
            self._check_prerequisites()
            self._create_directories()
            self._setup_python_environment()
            self._create_env_file()
            self._setup_nodejs_environment()
            self._verify_setup()

            log_success("Environment setup completed successfully!")
            self._print_next_steps()
            return True

        except Exception as e:
            log_error(f"Setup failed: {e}")
            return False

    def _check_prerequisites(self):
        """Check system prerequisites"""
        log_info("Checking prerequisites...")

        # Check Python version
        if sys.version_info < (3, 8):
            raise RuntimeError("Python 3.8+ required")

        log_success(f"Python version OK: {sys.version_info.major}.{sys.version_info.minor}")

        # Check for Node.js (optional)
        if shutil.which('node'):
            log_success("Node.js found")
        else:
            log_warning("Node.js not found - smart contract features may be limited")

        log_success("Prerequisites check passed")

    def _create_directories(self):
        """Create necessary directories"""
        log_info("Creating directory structure...")

        directories = [
            'bot/utils',
            'config', 
            'contracts/interfaces',
            'tests',
            'scripts',
            'docs',
            'logs',
            'data',
            'backups'
        ]

        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)

            # Create __init__.py for Python packages
            if 'bot' in directory or directory == 'tests':
                init_file = dir_path / '__init__.py'
                if not init_file.exists():
                    init_file.write_text("# Package initialization\n")

        log_success("Directory structure created")

    def _setup_python_environment(self):
        """Install Python dependencies"""
        log_info("Setting up Python environment...")

        # Install requirements if file exists
        requirements_file = self.project_root / 'requirements.txt'
        if requirements_file.exists():
            log_info("Installing Python dependencies...")
            try:
                subprocess.run([
                    sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)
                ], check=True)
                log_success("Python dependencies installed")
            except subprocess.CalledProcessError:
                log_warning("Some dependencies may have failed to install")
        else:
            log_info("Installing core dependencies...")
            core_packages = [
                'web3>=6.0.0',
                'python-dotenv',
                'requests',
                'aiohttp',
                'colorama',
                'pandas',
                'numpy'
            ]
            
            for package in core_packages:
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install', package], 
                                 capture_output=True, check=True)
                    log_success(f"Installed {package}")
                except subprocess.CalledProcessError:
                    log_warning(f"Failed to install {package}")

        log_success("Python environment setup complete")

    def _create_env_file(self):
        """Create .env file from template"""
        log_info("Setting up environment variables...")

        env_file = self.config_dir / '.env'
        env_template = self.config_dir / '.env.template'

        if not env_file.exists():
            if env_template.exists():
                log_info("Creating .env file from template...")
                shutil.copy(str(env_template), str(env_file))
            else:
                log_info("Creating default .env file...")
                default_env = """# Flashloan Arbitrage Bot Configuration

# Network RPC URLs  
POLYGON_RPC_URL=https://polygon-rpc.com/
MUMBAI_RPC_URL=https://rpc-mumbai.maticvigil.com/

# Your private key (TESTNET ONLY INITIALLY!)
PRIVATE_KEY=your_private_key_here

# API Keys
ETHERSCAN_API_KEY=your_etherscan_api_key
POLYGONSCAN_API_KEY=your_polygonscan_api_key
COINMARKETCAP_API_KEY=your_coinmarketcap_api_key

# Trading Configuration
MIN_PROFIT_USD=1.0
MAX_TRADE_SIZE_USD=1000
SLIPPAGE_TOLERANCE=0.5

# Risk Management
MAX_GAS_PRICE_GWEI=50
MAX_DAILY_TRADES=100

# Development
DEBUG=true
DRY_RUN=true
LOG_LEVEL=INFO
"""
                env_file.write_text(default_env)
            
            log_warning("Please edit config/.env with your API keys and settings")

        log_success("Environment file setup complete")

    def _setup_nodejs_environment(self):
        """Setup Node.js environment if available"""
        log_info("Setting up Node.js environment...")

        if not shutil.which('node'):
            log_warning("Node.js not available, skipping contract setup")
            return

        # Create basic package.json if it doesn't exist
        package_json = self.project_root / 'package.json'
        if not package_json.exists():
            log_info("Creating package.json...")
            package_data = {
                "name": "flashloan-arbitrage-bot",
                "version": "1.0.0",
                "description": "Flashloan Arbitrage Bot",
                "main": "index.js",
                "dependencies": {
                    "hardhat": "^2.19.2",
                    "@nomiclabs/hardhat-ethers": "^2.2.3",
                    "ethers": "^5.7.2"
                }
            }
            
            with open(package_json, 'w') as f:
                json.dump(package_data, f, indent=2)

        # Install dependencies
        try:
            log_info("Installing Node.js dependencies...")
            subprocess.run(['npm', 'install'], cwd=str(self.project_root), 
                         capture_output=True, check=True)
            log_success("Node.js dependencies installed")
        except subprocess.CalledProcessError:
            log_warning("Node.js dependency installation had issues")

        log_success("Node.js environment setup complete")

    def _verify_setup(self):
        """Verify setup is working correctly"""
        log_info("Verifying setup...")

        # Check critical files
        critical_files = [
            'config/.env'
        ]

        for file_path in critical_files:
            if (self.project_root / file_path).exists():
                log_success(f"Found: {file_path}")
            else:
                log_warning(f"Missing: {file_path}")

        # Test basic imports
        try:
            import web3
            log_success("Web3 import working")
        except ImportError:
            log_warning("Web3 not available - install with: pip install web3")

        try:
            from dotenv import load_dotenv
            log_success("python-dotenv import working")
        except ImportError:
            log_warning("python-dotenv not available - install with: pip install python-dotenv")

        log_success("Setup verification complete")

    def _print_next_steps(self):
        """Print next steps for user"""
        print("\n" + "=" * 60)
        print("NEXT STEPS:")
        print("=" * 60)
        print("1. Edit config/.env with your API keys:")
        print("   - POLYGON_RPC_URL (get from Alchemy/Infura)")
        print("   - PRIVATE_KEY (your wallet private key)")
        print("   - Add other API keys as needed")
        print("")
        print("2. Test the setup:")
        print("   python -c \"from bot.utils.logger import get_logger; print('Setup OK')\"")
        print("")
        print("3. Deploy smart contract (if Node.js available):")
        print("   python scripts/deploy_contract.py --network mumbai")
        print("")
        print("4. Start the bot:")
        print("   python bot/arbitrage_bot.py --dry-run")
        print("")
        print("5. For help with any issues, check the logs/ directory")
        print("=" * 60)


def main():
    """Main setup function"""
    try:
        setup = SafeEnvironmentSetup()
        success = setup.run_setup()

        if success:
            print("\nSetup completed successfully!")
        else:
            print("\nSetup failed. Please check the errors above.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nSetup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()