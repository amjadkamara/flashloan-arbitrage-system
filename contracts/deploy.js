// Deployment script 
const { ethers, network, run } = require("hardhat");
const { deployments } = require("hardhat");

// Polygon Mainnet Addresses
const POLYGON_ADDRESSES = {
    AAVE_V3_POOL: "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
    ONEINCH_ROUTER: "0x1111111254EEB25477B68fb85Ed929f73A960582",
    WMATIC: "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
    USDC: "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    USDT: "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
    DAI: "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
    WETH: "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
    WBTC: "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6"
};

// Mumbai Testnet Addresses
const MUMBAI_ADDRESSES = {
    AAVE_V3_POOL: "0x6C9fB0D5bD9429eb9Cd96B85B81d872281771E6B",
    ONEINCH_ROUTER: "0x1111111254EEB25477B68fb85Ed929f73A960582",
    WMATIC: "0x9c3C9283D3e44854697Cd22D3Faa240Cfb032889",
    USDC: "0xe6b8a5CF854791412c1f6EFC7CAf629f5Df1c747",
    USDT: "0xA02f6adc7926efeBBd59Fd43A84f4E0c0c91e832",
    DAI: "0xd393b1E02dA9831Ff419e22eA105aAe4c47E1253",
    WETH: "0xA6FA4fB5f76172d178d61B04b0ecd319C5d1C0aa"
};

async function main() {
    console.log("🚀 Starting FlashloanArbitrage deployment...");

    const [deployer] = await ethers.getSigners();
    const deployerAddress = await deployer.getAddress();
    const balance = await deployer.getBalance();

    console.log("📍 Network:", network.name);
    console.log("👤 Deployer:", deployerAddress);
    console.log("💰 Balance:", ethers.utils.formatEther(balance), "ETH");

    // Get network-specific addresses
    const isMainnet = network.name === "polygon" || network.name === "matic";
    const isTestnet = network.name === "mumbai" || network.name === "polygonMumbai";

    let addresses;
    if (isMainnet) {
        addresses = POLYGON_ADDRESSES;
        console.log("🔗 Using Polygon Mainnet addresses");
    } else if (isTestnet) {
        addresses = MUMBAI_ADDRESSES;
        console.log("🧪 Using Mumbai Testnet addresses");
    } else {
        throw new Error(`Unsupported network: ${network.name}`);
    }

    // Validate addresses exist
    console.log("\n🔍 Validating contract addresses...");
    for (const [name, address] of Object.entries(addresses)) {
        const code = await ethers.provider.getCode(address);
        if (code === "0x") {
            console.warn(`⚠️  Warning: No contract code at ${name}: ${address}`);
        } else {
            console.log(`✅ ${name}: ${address}`);
        }
    }

    // Deploy FlashloanArbitrage contract
    console.log("\n📦 Deploying FlashloanArbitrage contract...");

    const FlashloanArbitrage = await ethers.getContractFactory("FlashloanArbitrage");

    // Constructor parameters
    const constructorArgs = [
        addresses.AAVE_V3_POOL,    // Aave V3 Pool
        addresses.ONEINCH_ROUTER, // 1inch Router V5
        addresses.WMATIC,         // Wrapped MATIC
        deployerAddress           // Initial executor
    ];

    console.log("🏗️  Constructor arguments:");
    console.log("   - Aave V3 Pool:", constructorArgs[0]);
    console.log("   - 1inch Router:", constructorArgs[1]);
    console.log("   - WMATIC:", constructorArgs[2]);
    console.log("   - Initial Executor:", constructorArgs[3]);

    // Estimate gas for deployment
    const deployTransaction = await FlashloanArbitrage.getDeployTransaction(...constructorArgs);
    const estimatedGas = await ethers.provider.estimateGas(deployTransaction);
    const gasPrice = await ethers.provider.getGasPrice();
    const deploymentCost = estimatedGas.mul(gasPrice);

    console.log("⛽ Gas estimate:", estimatedGas.toString());
    console.log("💸 Deployment cost:", ethers.utils.formatEther(deploymentCost), "ETH");

    // Deploy contract
    const flashloanArbitrage = await FlashloanArbitrage.deploy(...constructorArgs);
    console.log("📋 Transaction hash:", flashloanArbitrage.deployTransaction.hash);

    // Wait for deployment
    console.log("⏳ Waiting for deployment confirmation...");
    const receipt = await flashloanArbitrage.deployed();

    console.log("🎉 FlashloanArbitrage deployed!");
    console.log("📍 Contract address:", flashloanArbitrage.address);
    console.log("🧾 Gas used:", receipt.deployTransaction.gasUsed?.toString());
    console.log("⚡ Block number:", receipt.deployTransaction.blockNumber);

    // Configure initial tokens
    console.log("\n🔧 Configuring initial supported tokens...");

    const tokensToAdd = [
        { name: "WMATIC", address: addresses.WMATIC, maxTradeSize: ethers.utils.parseEther("10000") },
        { name: "USDC", address: addresses.USDC, maxTradeSize: ethers.utils.parseUnits("50000", 6) },
        { name: "USDT", address: addresses.USDT, maxTradeSize: ethers.utils.parseUnits("50000", 6) },
        { name: "DAI", address: addresses.DAI, maxTradeSize: ethers.utils.parseEther("50000") },
    ];

    // Add WETH and WBTC for mainnet only
    if (isMainnet) {
        tokensToAdd.push(
            { name: "WETH", address: addresses.WETH, maxTradeSize: ethers.utils.parseEther("20") },
            { name: "WBTC", address: addresses.WBTC, maxTradeSize: ethers.utils.parseUnits("2", 8) }
        );
    } else if (addresses.WETH) {
        tokensToAdd.push(
            { name: "WETH", address: addresses.WETH, maxTradeSize: ethers.utils.parseEther("5") }
        );
    }

    // Add tokens one by one
    for (const token of tokensToAdd) {
        try {
            console.log(`Adding ${token.name} (${token.address})...`);
            const tx = await flashloanArbitrage.updateToken(
                token.address,
                true, // supported
                token.maxTradeSize
            );
            await tx.wait();
            console.log(`✅ ${token.name} configured`);
        } catch (error) {
            console.error(`❌ Failed to add ${token.name}:`, error.message);
        }
    }

    // Deploy Factory contract
    console.log("\n📦 Deploying FlashloanArbitrageFactory...");

    const FlashloanArbitrageFactory = await ethers.getContractFactory("FlashloanArbitrageFactory");
    const factory = await FlashloanArbitrageFactory.deploy();
    await factory.deployed();

    console.log("🏭 Factory deployed at:", factory.address);

    // Save deployment information
    const deploymentInfo = {
        network: network.name,
        timestamp: new Date().toISOString(),
        deployer: deployerAddress,
        contracts: {
            FlashloanArbitrage: {
                address: flashloanArbitrage.address,
                constructorArgs: constructorArgs,
                gasUsed: receipt.deployTransaction.gasUsed?.toString(),
                blockNumber: receipt.deployTransaction.blockNumber
            },
            FlashloanArbitrageFactory: {
                address: factory.address
            }
        },
        configuration: {
            supportedTokens: tokensToAdd,
            networkAddresses: addresses
        }
    };

    // Write deployment info to file
    const fs = require('fs');
    const path = require('path');
    const deploymentsDir = path.join(__dirname, '..', 'deployments');

    if (!fs.existsSync(deploymentsDir)) {
        fs.mkdirSync(deploymentsDir, { recursive: true });
    }

    const deploymentFile = path.join(deploymentsDir, `${network.name}_deployment.json`);
    fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));

    console.log("💾 Deployment info saved to:", deploymentFile);

    // Verify contracts on polygonscan (if not local network)
    if (network.name !== "hardhat" && network.name !== "localhost") {
        console.log("\n🔍 Waiting before contract verification...");
        await new Promise(resolve => setTimeout(resolve, 30000)); // Wait 30 seconds

        try {
            console.log("🔍 Verifying FlashloanArbitrage contract...");
            await run("verify:verify", {
                address: flashloanArbitrage.address,
                constructorArguments: constructorArgs,
            });
            console.log("✅ FlashloanArbitrage verified!");
        } catch (error) {
            console.warn("⚠️  Verification failed:", error.message);
        }

        try {
            console.log("🔍 Verifying FlashloanArbitrageFactory contract...");
            await run("verify:verify", {
                address: factory.address,
                constructorArguments: [],
            });
            console.log("✅ Factory verified!");
        } catch (error) {
            console.warn("⚠️  Factory verification failed:", error.message);
        }
    }

    // Display final summary
    console.log("\n🎉 DEPLOYMENT COMPLETE!");
    console.log("=====================================");
    console.log("Network:", network.name);
    console.log("FlashloanArbitrage:", flashloanArbitrage.address);
    console.log("Factory:", factory.address);
    console.log("Deployer:", deployerAddress);
    console.log("=====================================");

    // Display next steps
    console.log("\n📋 NEXT STEPS:");
    console.log("1. Update bot/config/addresses.py with new contract address");
    console.log("2. Fund the contract with initial MATIC for gas");
    console.log("3. Configure additional executors if needed");
    console.log("4. Test with small amounts first");
    console.log("5. Monitor logs and adjust parameters as needed");

    // Create environment file template
    const envTemplate = `
# Add these to your .env file:
FLASHLOAN_CONTRACT_ADDRESS=${flashloanArbitrage.address}
FACTORY_CONTRACT_ADDRESS=${factory.address}
AAVE_V3_POOL_ADDRESS=${addresses.AAVE_V3_POOL}
ONEINCH_ROUTER_ADDRESS=${addresses.ONEINCH_ROUTER}
WMATIC_ADDRESS=${addresses.WMATIC}
DEPLOYMENT_BLOCK=${receipt.deployTransaction.blockNumber}
`;

    const envFile = path.join(__dirname, '..', 'config', '.env.deployment');
    fs.writeFileSync(envFile, envTemplate.trim());
    console.log("💾 Environment template saved to:", envFile);

    return {
        flashloanArbitrage: flashloanArbitrage.address,
        factory: factory.address,
        deploymentInfo
    };
}

// Handle errors
main()
    .then((result) => {
        console.log("\n✅ Script completed successfully!");
        process.exit(0);
    })
    .catch((error) => {
        console.error("\n❌ Deployment failed:");
        console.error(error);
        process.exit(1);
    });

module.exports = { main };