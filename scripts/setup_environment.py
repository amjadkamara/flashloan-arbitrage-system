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
sys.path.append(str(Path(__file__).parent.parent))

from bot.utils.logger import get_logger
from config.settings import load_settings

logger = get_logger('setup_environment')


class EnvironmentSetup:
    """Handles automated environment setup"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_dir = self.project_root / 'config'
        self.contracts_dir = self.project_root / 'contracts'

    def run_setup(self) -> bool:
        """Run complete environment setup"""
        logger.info("🚀 Starting Flashloan Arbitrage Bot Setup")

        try:
            # Setup steps
            self._check_prerequisites()
            self._setup_python_environment()
            self._create_env_file()
            self._setup_nodejs_environment()
            self._compile_contracts()
            self._verify_setup()

            logger.success("✅ Environment setup completed successfully!")
            self._print_next_steps()
            return True

        except Exception as e:
            logger.error(f"❌ Setup failed: {e}")
            return False

    def _check_prerequisites(self):
        """Check system prerequisites"""
        logger.info("📋 Checking prerequisites...")

        # Check Python version
        if sys.version_info < (3, 8):
            raise RuntimeError("Python 3.8+ required")

        # Check for required commands
        required_commands = ['node', 'npm', 'git']
        for cmd in required_commands:
            if not shutil.which(cmd):
                raise RuntimeError(f"Required command not found: {cmd}")

        logger.success("✅ Prerequisites check passed")

    def _setup_python_environment(self):
        """Setup Python virtual environment and dependencies"""
        logger.info("🐍 Setting up Python environment...")

        # Check if virtual environment exists
        venv_path = self.project_root / 'venv'
        if not venv_path.exists():
            logger.info("Creating virtual environment...")
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)

        # Install requirements
        requirements_file = self.project_root / 'requirements.txt'
        if requirements_file.exists():
            logger.info("Installing Python dependencies...")
            pip_path = venv_path / ('Scripts' if os.name == 'nt' else 'bin') / 'pip'
            subprocess.run([str(pip_path), 'install', '-r', str(requirements_file)], check=True)

        logger.success("✅ Python environment setup complete")

    def _create_env_file(self):
        """Create .env file from template"""
        logger.info("⚙️ Setting up environment variables...")

        env_template = self.config_dir / '.env.template'
        env_file = self.config_dir / '.env'

        if not env_file.exists() and env_template.exists():
            logger.info("Creating .env file from template...")
            shutil.copy(str(env_template), str(env_file))
            logger.warning("📝 Please edit config/.env with your API keys and settings")

        logger.success("✅ Environment file setup complete")

    def _setup_nodejs_environment(self):
        """Setup Node.js environment and dependencies"""
        logger.info("📦 Setting up Node.js environment...")

        # Check if package.json exists
        package_json = self.project_root / 'package.json'
        if package_json.exists():
            logger.info("Installing Node.js dependencies...")
            subprocess.run(['npm', 'install'], cwd=str(self.project_root), check=True)

        logger.success("✅ Node.js environment setup complete")

    def _compile_contracts(self):
        """Compile smart contracts"""
        logger.info("🔨 Compiling smart contracts...")

        try:
            # Check if Hardhat is available
            subprocess.run(['npx', 'hardhat', '--version'],
                           cwd=str(self.project_root),
                           check=True,
                           capture_output=True)

            # Compile contracts
            result = subprocess.run(['npx', 'hardhat', 'compile'],
                                    cwd=str(self.project_root),
                                    capture_output=True,
                                    text=True)

            if result.returncode == 0:
                logger.success("✅ Smart contracts compiled successfully")
            else:
                logger.warning(f"⚠️ Contract compilation issues: {result.stderr}")

        except subprocess.CalledProcessError:
            logger.warning("⚠️ Hardhat not available, skipping contract compilation")

    def _verify_setup(self):
        """Verify setup is working correctly"""
        logger.info("🔍 Verifying setup...")

        # Check critical files
        critical_files = [
            'config/.env',
            'config/settings.py',
            'config/addresses.py',
            'bot/arbitrage_bot.py',
            'bot/opportunity_scanner.py',
            'requirements.txt'
        ]

        missing_files = []
        for file_path in critical_files:
            if not (self.project_root / file_path).exists():
                missing_files.append(file_path)

        if missing_files:
            logger.warning(f"⚠️ Missing files: {', '.join(missing_files)}")

        # Try importing main components
        try:
            from bot.arbitrage_bot import FlashloanArbitrageBot
            logger.success("✅ Bot imports working correctly")
        except ImportError as e:
            logger.warning(f"⚠️ Import issue: {e}")

    def _print_next_steps(self):
        """Print next steps for user"""
        logger.info("\n" + "=" * 60)
        logger.info("🎯 NEXT STEPS:")
        logger.info("=" * 60)
        logger.info("1. Edit config/.env with your API keys:")
        logger.info("   - WEB3_PROVIDER_URL (Polygon RPC)")
        logger.info("   - PRIVATE_KEY (wallet private key)")
        logger.info("   - API keys for price feeds")
        logger.info("")
        logger.info("2. Deploy the smart contract:")
        logger.info("   python scripts/deploy_contract.py")
        logger.info("")
        logger.info("3. Test the bot:")
        logger.info("   python -m pytest tests/ -v")
        logger.info("")
        logger.info("4. Start the bot:")
        logger.info("   python bot/arbitrage_bot.py")
        logger.info("")
        logger.info("5. Monitor performance:")
        logger.info("   python scripts/monitor_performance.py")
        logger.info("=" * 60)


def setup_directory_structure():
    """Create missing directories"""
    logger.info("📁 Setting up directory structure...")

    project_root = Path(__file__).parent.parent
    directories = [
        'bot/utils',
        'config',
        'contracts/interfaces',
        'tests',
        'scripts',
        'docs',
        'logs',
        'data'
    ]

    for directory in directories:
        dir_path = project_root / directory
        dir_path.mkdir(parents=True, exist_ok=True)

        # Create __init__.py for Python packages
        if 'bot' in directory:
            init_file = dir_path / '__init__.py'
            if not init_file.exists():
                init_file.write_text("# Package initialization\n")

    logger.success("✅ Directory structure created")


def create_activation_scripts():
    """Create environment activation scripts"""
    logger.info("📝 Creating activation scripts...")

    project_root = Path(__file__).parent.parent

    # Windows activation script
    if os.name == 'nt':
        activate_script = project_root / 'activate.bat'
        activate_content = f'''@echo off
cd /d "{project_root}"
call venv\\Scripts\\activate.bat
echo Flashloan Arbitrage Bot Environment Activated
echo.
echo Available commands:
echo   python bot/arbitrage_bot.py          - Start the bot
echo   python scripts/monitor_performance.py - Monitor performance
echo   python -m pytest tests/ -v           - Run tests
echo   python scripts/deploy_contract.py    - Deploy contract
echo.
'''
        activate_script.write_text(activate_content)

    # Unix activation script
    else:
        activate_script = project_root / 'activate.sh'
        activate_content = f'''#!/bin/bash
cd "{project_root}"
source venv/bin/activate
echo "Flashloan Arbitrage Bot Environment Activated"
echo ""
echo "Available commands:"
echo "  python bot/arbitrage_bot.py          - Start the bot"
echo "  python scripts/monitor_performance.py - Monitor performance"
echo "  python -m pytest tests/ -v           - Run tests"
echo "  python scripts/deploy_contract.py    - Deploy contract"
echo ""
'''
        activate_script.write_text(activate_content)
        os.chmod(activate_script, 0o755)

    logger.success("✅ Activation scripts created")


def main():
    """Main setup function"""
    try:
        # Create directory structure first
        setup_directory_structure()

        # Create activation scripts
        create_activation_scripts()

        # Run main setup
        setup = EnvironmentSetup()
        success = setup.run_setup()

        if success:
            logger.info("\n🎉 Setup completed successfully!")
            logger.info("Run the activation script to get started:")
            if os.name == 'nt':
                logger.info("   activate.bat")
            else:
                logger.info("   source activate.sh")
        else:
            logger.error("\n❌ Setup failed. Please check the errors above.")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\n⏹️ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()