// Hardhat configuration 
// hardhat.config.js
require("@nomicfoundation/hardhat-toolbox");
require("@nomicfoundation/hardhat-verify");
require("hardhat-gas-reporter");
require("hardhat-contract-sizer");
require("solidity-coverage");
require("dotenv").config();

// Get environment variables
const PRIVATE_KEY = process.env.PRIVATE_KEY || "0x" + "00".repeat(32);
const POLYGON_RPC_URL = process.env.POLYGON_RPC_URL || "https://polygon-rpc.com";
const MUMBAI_RPC_URL = process.env.MUMBAI_RPC_URL || "https://rpc-mumbai.matic.today";
const POLYGONSCAN_API_KEY = process.env.POLYGONSCAN_API_KEY || "";
const COINMARKETCAP_API_KEY = process.env.COINMARKETCAP_API_KEY || "";
const REPORT_GAS = process.env.REPORT_GAS || false;

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
  version: "0.8.20",
  settings: {
    optimizer: {
      enabled: true,
      runs: 1000,  // Change from 200 to 1000
      details: {
        yul: true,  // Change from false to true
      },
    },
    viaIR: true,
  },
},

  networks: {
    // Local development network
    hardhat: {
      chainId: 31337,
      gas: 12000000,
      blockGasLimit: 12000000,
      allowUnlimitedContractSize: true,
      timeout: 1800000,
      forking: {
        url: POLYGON_RPC_URL,
        // blockNumber: 50000000, // Pin to specific block for consistent testing
      },
      accounts: {
        count: 20,
        accountsBalance: "10000000000000000000000", // 10,000 ETH
      },
    },

    // Local node for testing
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337,
      gas: 12000000,
      timeout: 1800000,
    },

    // Polygon Mainnet
    polygon: {
      url: POLYGON_RPC_URL,
      chainId: 137,
      accounts: PRIVATE_KEY !== "0x" + "00".repeat(32) ? [PRIVATE_KEY] : [],
      gas: 20000000,
      gasPrice: 50000000000, // 50 gwei
      timeout: 1800000,
    },

    // Mumbai Testnet
    mumbai: {
      url: MUMBAI_RPC_URL,
      chainId: 80001,
      accounts: PRIVATE_KEY !== "0x" + "00".repeat(32) ? [PRIVATE_KEY] : [],
      gas: 20000000,
      gasPrice: 10000000000, // 10 gwei
      timeout: 1800000,
    },
  },

  // Contract verification
  etherscan: {
    apiKey: {
      polygon: POLYGONSCAN_API_KEY,
      polygonMumbai: POLYGONSCAN_API_KEY,
    },
    customChains: [
      {
        network: "polygon",
        chainId: 137,
        urls: {
          apiURL: "https://api.polygonscan.com/api",
          browserURL: "https://polygonscan.com/"
        }
      }
    ]
  },

  // Gas reporting
  gasReporter: {
    enabled: REPORT_GAS,
    currency: "USD",
    gasPrice: 50, // gwei
    coinmarketcap: COINMARKETCAP_API_KEY,
    token: "MATIC",
    showTimeSpent: true,
    showMethodSig: true,
    maxMethodDiff: 10,
    excludeContracts: ["Mock", "Test"],
  },

  // Contract size
  contractSizer: {
    alphaSort: true,
    disambiguatePaths: false,
    runOnCompile: true,
    strict: false,
    only: ["FlashloanArbitrage"],
  },

  // Test configuration
  mocha: {
    timeout: 300000, // 5 minutes
  },

  // Path configurations
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },

  // TypeChain configuration
  typechain: {
    outDir: "typechain-types",
    target: "ethers-v6",
  },
};

// Custom tasks
task("accounts", "Prints the list of accounts", async (taskArgs, hre) => {
  const accounts = await hre.ethers.getSigners();

  for (const account of accounts) {
    console.log(account.address);
  }
});

task("balance", "Prints an account's balance")
  .addParam("account", "The account's address")
  .setAction(async (taskArgs, hre) => {
    const balance = await hre.ethers.provider.getBalance(taskArgs.account);
    console.log(hre.ethers.formatEther(balance), "MATIC");
  });

task("block-number", "Prints the current block number", async (taskArgs, hre) => {
  const blockNumber = await hre.ethers.provider.getBlockNumber();
  console.log("Current block number:", blockNumber);
});

task("gas-price", "Prints the current gas price", async (taskArgs, hre) => {
  const gasPrice = await hre.ethers.provider.getGasPrice();
  console.log("Current gas price:", hre.ethers.formatUnits(gasPrice, "gwei"), "gwei");
});

task("deploy-arbitrage", "Deploy the FlashloanArbitrage contract")
  .addOptionalParam("verify", "Verify contract on Etherscan", false, types.boolean)
  .setAction(async (taskArgs, hre) => {
    const { deploy } = require("./contracts/deploy.js");
    await deploy(hre, taskArgs.verify);
  });

task("verify-contract", "Verify contract on Etherscan")
  .addParam("address", "Contract address")
  .addParam("args", "Constructor arguments (JSON array)")
  .setAction(async (taskArgs, hre) => {
    const args = JSON.parse(taskArgs.args);
    await hre.run("verify:verify", {
      address: taskArgs.address,
      constructorArguments: args,
    });
  });

// Network helpers
task("setup-local", "Setup local development environment")
  .setAction(async (taskArgs, hre) => {
    console.log("Setting up local development environment...");

    // Fund accounts with MATIC
    const accounts = await hre.ethers.getSigners();
    console.log(`Loaded ${accounts.length} accounts`);

    // Get current block
    const blockNumber = await hre.ethers.provider.getBlockNumber();
    console.log(`Current block: ${blockNumber}`);

    // Check if we're forking
    if (hre.network.config.forking) {
      console.log(`Forking from: ${hre.network.config.forking.url}`);
    }

    console.log("Local environment ready!");
  });