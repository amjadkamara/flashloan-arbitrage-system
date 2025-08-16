// ✅ Main arbitrage contract (created) 
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "./interfaces/IAavePool.sol";
import "./interfaces/I1InchRouter.sol";
import "./interfaces/IDEX.sol";

/**
 * @title FlashloanArbitrage
 * @dev Automated arbitrage contract using Aave V3 flashloans
 * @notice This contract executes arbitrage opportunities between different DEXs on Polygon
 */
contract FlashloanArbitrage is Ownable, ReentrancyGuard, Pausable, IFlashLoanReceiver {
    using SafeERC20 for IERC20;

    // =============================================================================
    // STATE VARIABLES
    // =============================================================================

    /// @dev Aave V3 Pool contract
    IAavePool public immutable AAVE_POOL;

    /// @dev 1inch Router contract
    I1InchRouter public immutable ONEINCH_ROUTER;

    /// @dev Wrapped MATIC token
    address public immutable WMATIC;

    /// @dev Maximum gas price allowed for transactions (in wei)
    uint256 public maxGasPrice = 100 gwei;

    /// @dev Minimum profit percentage required (in basis points, 100 = 1%)
    uint256 public minProfitBasisPoints = 100;

    /// @dev Maximum slippage tolerance (in basis points, 50 = 0.5%)
    uint256 public maxSlippageBasisPoints = 50;

    /// @dev Fee percentage for the contract owner (in basis points, 20 = 0.2%)
    uint256 public ownerFeeBasisPoints = 20;

    /// @dev Mapping to track authorized executors
    mapping(address => bool) public authorizedExecutors;

    /// @dev Mapping to track supported tokens
    mapping(address => bool) public supportedTokens;

    /// @dev Emergency pause flag for specific tokens
    mapping(address => bool) public tokenPaused;

    /// @dev Total profits generated (for tracking)
    uint256 public totalProfits;

    /// @dev Total trades executed
    uint256 public totalTrades;

    /// @dev Maximum trade size per token
    mapping(address => uint256) public maxTradeSize;

    // =============================================================================
    // STRUCTS
    // =============================================================================

    /**
     * @dev Arbitrage parameters for execution
     * @param tokenIn Input token address
     * @param tokenOut Output token address
     * @param amountIn Amount of input tokens
     * @param minAmountOut Minimum expected output amount
     * @param dex1Router Router address for first DEX
     * @param dex2Router Router address for second DEX
     * @param dex1Data Calldata for first DEX swap
     * @param dex2Data Calldata for second DEX swap
     * @param flashloanAsset Asset to flashloan
     * @param flashloanAmount Amount to flashloan
     */
    struct ArbitrageParams {
        address tokenIn;
        address tokenOut;
        uint256 amountIn;
        uint256 minAmountOut;
        address dex1Router;
        address dex2Router;
        bytes dex1Data;
        bytes dex2Data;
        address flashloanAsset;
        uint256 flashloanAmount;
    }

    /**
     * @dev Trade execution result
     * @param success Whether trade was successful
     * @param profit Profit generated (can be negative for losses)
     * @param gasUsed Gas consumed
     * @param dex1AmountOut Amount received from DEX1
     * @param dex2AmountOut Amount received from DEX2
     */
    struct TradeResult {
        bool success;
        int256 profit;
        uint256 gasUsed;
        uint256 dex1AmountOut;
        uint256 dex2AmountOut;
    }

    // =============================================================================
    // EVENTS
    // =============================================================================

    event ArbitrageExecuted(
        address indexed tokenIn,
        address indexed tokenOut,
        uint256 amountIn,
        uint256 profit,
        address executor,
        uint256 gasUsed
    );

    event FlashloanExecuted(
        address indexed asset,
        uint256 amount,
        uint256 premium,
        bool success
    );

    event ProfitWithdrawn(
        address indexed token,
        uint256 amount,
        address indexed recipient
    );

    event ParametersUpdated(
        uint256 minProfitBasisPoints,
        uint256 maxSlippageBasisPoints,
        uint256 maxGasPrice
    );

    event ExecutorUpdated(address indexed executor, bool authorized);

    event TokenUpdated(address indexed token, bool supported, uint256 maxTradeSize);

    event EmergencyWithdrawal(address indexed token, uint256 amount);

    // =============================================================================
    // CONSTRUCTOR
    // =============================================================================

    /**
     * @dev Initialize the arbitrage contract
     * @param _aavePool Address of Aave V3 Pool
     * @param _oneinchRouter Address of 1inch Router
     * @param _wmatic Address of wrapped MATIC token
     * @param _initialExecutor Initial authorized executor address
     */
    constructor(
        address _aavePool,
        address _oneinchRouter,
        address _wmatic,
        address _initialExecutor
    ) {
        require(_aavePool != address(0), "Invalid Aave pool address");
        require(_oneinchRouter != address(0), "Invalid 1inch router address");
        require(_wmatic != address(0), "Invalid WMATIC address");
        require(_initialExecutor != address(0), "Invalid executor address");

        AAVE_POOL = IAavePool(_aavePool);
        ONEINCH_ROUTER = I1InchRouter(_oneinchRouter);
        WMATIC = _wmatic;

        // Set initial executor
        authorizedExecutors[_initialExecutor] = true;

        // Set initial supported tokens (common tokens on Polygon)
        supportedTokens[_wmatic] = true; // WMATIC
        maxTradeSize[_wmatic] = 10000 ether; // 10,000 MATIC
    }

    // =============================================================================
    // MODIFIERS
    // =============================================================================

    /**
     * @dev Ensures only authorized executors can call the function
     */
    modifier onlyExecutor() {
        require(authorizedExecutors[msg.sender] || msg.sender == owner(), "Not authorized executor");
        _;
    }

    /**
     * @dev Ensures gas price is within limits
     */
    modifier gasLimitCheck() {
        require(tx.gasprice <= maxGasPrice, "Gas price too high");
        _;
    }

    /**
     * @dev Ensures token is supported
     */
    modifier onlySupported(address token) {
        require(supportedTokens[token], "Token not supported");
        require(!tokenPaused[token], "Token trading paused");
        _;
    }

    // =============================================================================
    // MAIN ARBITRAGE FUNCTIONS
    // =============================================================================

    /**
     * @dev Executes arbitrage using flashloan
     * @param params Arbitrage parameters
     * @return result Trade execution result
     */
    function executeArbitrage(ArbitrageParams calldata params)
        external
        onlyExecutor
        whenNotPaused
        nonReentrant
        gasLimitCheck
        onlySupported(params.flashloanAsset)
        returns (TradeResult memory result)
    {
        uint256 startGas = gasleft();

        // Validate parameters
        require(params.flashloanAmount > 0, "Invalid flashloan amount");
        require(params.flashloanAmount <= maxTradeSize[params.flashloanAsset], "Amount exceeds max trade size");
        require(params.minAmountOut > 0, "Invalid min amount out");

        // Prepare flashloan
        address[] memory assets = new address[](1);
        uint256[] memory amounts = new uint256[](1);
        uint256[] memory interestRateModes = new uint256[](1);

        assets[0] = params.flashloanAsset;
        amounts[0] = params.flashloanAmount;
        interestRateModes[0] = 0; // No debt, we'll repay immediately

        // Encode arbitrage parameters for flashloan callback
        bytes memory encodedParams = abi.encode(params, msg.sender, startGas);

        // Execute flashloan
        try AAVE_POOL.flashLoan(
            address(this),
            assets,
            amounts,
            interestRateModes,
            address(this),
            encodedParams,
            0 // No referral code
        ) {
            result.success = true;
        } catch Error(string memory reason) {
            emit ArbitrageExecuted(
                params.tokenIn,
                params.tokenOut,
                params.amountIn,
                0,
                msg.sender,
                startGas - gasleft()
            );
            revert(reason);
        }

        totalTrades++;
        return result;
    }

    /**
     * @dev Flashloan callback - executes the actual arbitrage
     * @param assets Array of flashloaned assets
     * @param amounts Array of flashloaned amounts
     * @param premiums Array of flashloan premiums
     * @param initiator Address that initiated the flashloan
     * @param params Encoded arbitrage parameters
     * @return success True if arbitrage was successful
     */
    function executeOperation(
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata premiums,
        address initiator,
        bytes calldata params
    ) external override returns (bool success) {
        require(msg.sender == address(AAVE_POOL), "Caller must be Aave pool");
        require(initiator == address(this), "Invalid flashloan initiator");

        // Decode parameters
        (ArbitrageParams memory arbParams, address executor, uint256 startGas) =
            abi.decode(params, (ArbitrageParams, address, uint256));

        address flashloanAsset = assets[0];
        uint256 flashloanAmount = amounts[0];
        uint256 flashloanPremium = premiums[0];

        emit FlashloanExecuted(flashloanAsset, flashloanAmount, flashloanPremium, true);

        // Execute arbitrage logic
        int256 profit = _executeArbitrageLogic(
            arbParams,
            flashloanAsset,
            flashloanAmount,
            flashloanPremium
        );

        // Approve flashloan repayment
        uint256 amountOwing = flashloanAmount + flashloanPremium;
        IERC20(flashloanAsset).safeApprove(address(AAVE_POOL), amountOwing);

        // Check if we have enough to repay
        uint256 balance = IERC20(flashloanAsset).balanceOf(address(this));
        require(balance >= amountOwing, "Insufficient balance to repay flashloan");

        // Update stats
        if (profit > 0) {
            totalProfits += uint256(profit);
        }

        uint256 gasUsed = startGas - gasleft();

        emit ArbitrageExecuted(
            arbParams.tokenIn,
            arbParams.tokenOut,
            arbParams.amountIn,
            uint256(profit),
            executor,
            gasUsed
        );

        return true;
    }

    /**
     * @dev Internal function to execute arbitrage logic
     * @param params Arbitrage parameters
     * @param flashloanAsset Asset that was flashloaned
     * @param flashloanAmount Amount that was flashloaned
     * @param flashloanPremium Premium for the flashloan
     * @return profit Net profit from arbitrage (can be negative)
     */
    function _executeArbitrageLogic(
        ArbitrageParams memory params,
        address flashloanAsset,
        uint256 flashloanAmount,
        uint256 flashloanPremium
    ) internal returns (int256 profit) {
        uint256 initialBalance = IERC20(flashloanAsset).balanceOf(address(this));

        try this._performSwaps(params) returns (uint256 finalAmount) {
            uint256 finalBalance = IERC20(flashloanAsset).balanceOf(address(this));
            uint256 totalCost = flashloanAmount + flashloanPremium;

            if (finalBalance >= totalCost) {
                profit = int256(finalBalance - totalCost);

                // Calculate and transfer owner fee
                if (profit > 0 && ownerFeeBasisPoints > 0) {
                    uint256 ownerFee = (uint256(profit) * ownerFeeBasisPoints) / 10000;
                    if (ownerFee > 0) {
                        IERC20(flashloanAsset).safeTransfer(owner(), ownerFee);
                        profit -= int256(ownerFee);
                    }
                }
            } else {
                profit = int256(finalBalance) - int256(totalCost);
            }
        } catch Error(string memory reason) {
            // If swaps fail, we still need to repay the flashloan
            profit = -int256(flashloanPremium);
            revert(string(abi.encodePacked("Arbitrage failed: ", reason)));
        }
    }

    /**
     * @dev Performs the actual token swaps (external for try-catch)
     * @param params Arbitrage parameters
     * @return finalAmount Final amount received after swaps
     */
    function _performSwaps(ArbitrageParams calldata params)
        external
        returns (uint256 finalAmount)
    {
        require(msg.sender == address(this), "Internal function");

        // First swap: Use flashloaned tokens to buy intermediate token
        if (params.dex1Router == address(ONEINCH_ROUTER)) {
            // Use 1inch for first swap
            _execute1inchSwap(params.tokenIn, params.tokenOut, params.amountIn, params.dex1Data);
        } else {
            // Use other DEX for first swap
            _executeGenericSwap(params.dex1Router, params.dex1Data);
        }

        uint256 intermediateBalance = IERC20(params.tokenOut).balanceOf(address(this));
        require(intermediateBalance >= params.minAmountOut, "Insufficient intermediate amount");

        // Second swap: Convert back to original token
        if (params.dex2Router == address(ONEINCH_ROUTER)) {
            // Use 1inch for second swap
            _execute1inchSwap(params.tokenOut, params.tokenIn, intermediateBalance, params.dex2Data);
        } else {
            // Use other DEX for second swap
            _executeGenericSwap(params.dex2Router, params.dex2Data);
        }

        finalAmount = IERC20(params.tokenIn).balanceOf(address(this));
    }

    /**
     * @dev Executes swap using 1inch router
     * @param tokenIn Input token address
     * @param tokenOut Output token address
     * @param amountIn Input amount
     * @param swapData Encoded swap data for 1inch
     */
    function _execute1inchSwap(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        bytes memory swapData
    ) internal {
        IERC20(tokenIn).safeApprove(address(ONEINCH_ROUTER), amountIn);

        (bool success, bytes memory returnData) = address(ONEINCH_ROUTER).call(swapData);
        require(success, "1inch swap failed");

        // Reset approval
        IERC20(tokenIn).safeApprove(address(ONEINCH_ROUTER), 0);
    }

    /**
     * @dev Executes swap using generic router
     * @param router Router address
     * @param swapData Encoded swap data
     */
    function _executeGenericSwap(address router, bytes memory swapData) internal {
        (bool success, bytes memory returnData) = router.call(swapData);
        require(success, "Generic swap failed");
    }

    // =============================================================================
    // VIEW FUNCTIONS
    // =============================================================================

    /**
     * @dev Calculates potential profit for given arbitrage parameters
     * @param params Arbitrage parameters
     * @return estimatedProfit Estimated profit (can be negative)
     * @return profitable Whether the arbitrage would be profitable
     */
    function calculateProfit(ArbitrageParams calldata params)
        external
        view
        returns (int256 estimatedProfit, bool profitable)
    {
        // This is a simplified calculation - in practice, you'd want to
        // query actual DEX prices and factor in slippage, gas costs, etc.

        uint256 flashloanPremium = (params.flashloanAmount * AAVE_POOL.FLASHLOAN_PREMIUM_TOTAL()) / 10000;
        uint256 estimatedGasCost = tx.gasprice * 500000; // Estimate 500k gas

        // For now, return basic calculation
        // In production, implement proper price queries
        estimatedProfit = int256(params.minAmountOut) - int256(params.amountIn) - int256(flashloanPremium) - int256(estimatedGasCost);
        profitable = estimatedProfit > 0;
    }

    /**
     * @dev Gets contract statistics
     * @return totalTrades_ Total number of trades executed
     * @return totalProfits_ Total profits generated
     * @return contractBalance Current contract balance of specified token
     */
    function getStats(address token)
        external
        view
        returns (
            uint256 totalTrades_,
            uint256 totalProfits_,
            uint256 contractBalance
        )
    {
        totalTrades_ = totalTrades;
        totalProfits_ = totalProfits;
        contractBalance = IERC20(token).balanceOf(address(this));
    }

    // =============================================================================
    // OWNER FUNCTIONS
    // =============================================================================

    /**
     * @dev Updates contract parameters
     * @param _minProfitBasisPoints New minimum profit in basis points
     * @param _maxSlippageBasisPoints New maximum slippage in basis points
     * @param _maxGasPrice New maximum gas price in wei
     */
    function updateParameters(
        uint256 _minProfitBasisPoints,
        uint256 _maxSlippageBasisPoints,
        uint256 _maxGasPrice
    ) external onlyOwner {
        require(_minProfitBasisPoints <= 1000, "Min profit too high"); // Max 10%
        require(_maxSlippageBasisPoints <= 500, "Max slippage too high"); // Max 5%
        require(_maxGasPrice >= 1 gwei, "Gas price too low");

        minProfitBasisPoints = _minProfitBasisPoints;
        maxSlippageBasisPoints = _maxSlippageBasisPoints;
        maxGasPrice = _maxGasPrice;

        emit ParametersUpdated(_minProfitBasisPoints, _maxSlippageBasisPoints, _maxGasPrice);
    }

    /**
     * @dev Updates executor authorization
     * @param executor Address of the executor
     * @param authorized Whether the executor should be authorized
     */
    function updateExecutor(address executor, bool authorized) external onlyOwner {
        require(executor != address(0), "Invalid executor address");
        authorizedExecutors[executor] = authorized;
        emit ExecutorUpdated(executor, authorized);
    }

    /**
     * @dev Updates token support and trading limits
     * @param token Token address
     * @param supported Whether token should be supported
     * @param _maxTradeSize Maximum trade size for this token
     */
    function updateToken(
        address token,
        bool supported,
        uint256 _maxTradeSize
    ) external onlyOwner {
        require(token != address(0), "Invalid token address");

        supportedTokens[token] = supported;
        if (supported) {
            require(_maxTradeSize > 0, "Max trade size must be positive");
            maxTradeSize[token] = _maxTradeSize;
        }

        emit TokenUpdated(token, supported, _maxTradeSize);
    }

    /**
     * @dev Pauses or unpauses trading for a specific token
     * @param token Token address
     * @param paused Whether token trading should be paused
     */
    function pauseToken(address token, bool paused) external onlyOwner {
        tokenPaused[token] = paused;
    }

    /**
     * @dev Updates owner fee percentage
     * @param _ownerFeeBasisPoints New owner fee in basis points
     */
    function updateOwnerFee(uint256 _ownerFeeBasisPoints) external onlyOwner {
        require(_ownerFeeBasisPoints <= 100, "Owner fee too high"); // Max 1%
        ownerFeeBasisPoints = _ownerFeeBasisPoints;
    }

    /**
     * @dev Withdraws profits accumulated in the contract
     * @param token Token address to withdraw
     * @param amount Amount to withdraw (0 for all)
     * @param recipient Address to receive the tokens
     */
    function withdrawProfits(
        address token,
        uint256 amount,
        address recipient
    ) external onlyOwner {
        require(recipient != address(0), "Invalid recipient");

        uint256 balance = IERC20(token).balanceOf(address(this));
        require(balance > 0, "No balance to withdraw");

        uint256 withdrawAmount = amount == 0 ? balance : amount;
        require(withdrawAmount <= balance, "Insufficient balance");

        IERC20(token).safeTransfer(recipient, withdrawAmount);
        emit ProfitWithdrawn(token, withdrawAmount, recipient);
    }

    /**
     * @dev Emergency withdrawal function (only when paused)
     * @param token Token address to withdraw
     * @param recipient Address to receive tokens
     */
    function emergencyWithdraw(address token, address recipient) external onlyOwner whenPaused {
        require(recipient != address(0), "Invalid recipient");

        uint256 balance = IERC20(token).balanceOf(address(this));
        if (balance > 0) {
            IERC20(token).safeTransfer(recipient, balance);
            emit EmergencyWithdrawal(token, balance);
        }
    }

    /**
     * @dev Pauses the contract
     */
    function pause() external onlyOwner {
        _pause();
    }

    /**
     * @dev Unpauses the contract
     */
    function unpause() external onlyOwner {
        _unpause();
    }

    // =============================================================================
    // UTILITY FUNCTIONS
    // =============================================================================

    /**
     * @dev Allows contract to receive ETH
     */
    receive() external payable {
        // Allow contract to receive ETH for gas refunds or WMATIC unwrapping
    }

    /**
     * @dev Emergency ETH withdrawal
     * @param recipient Address to receive ETH
     */
    function withdrawETH(address payable recipient) external onlyOwner {
        require(recipient != address(0), "Invalid recipient");
        uint256 balance = address(this).balance;
        if (balance > 0) {
            (bool success, ) = recipient.call{value: balance}("");
            require(success, "ETH transfer failed");
        }
    }

    /**
     * @dev Batch function to execute multiple operations
     * @param calls Array of encoded function calls
     * @return results Array of call results
     */
    function batch(bytes[] calldata calls) external onlyOwner returns (bytes[] memory results) {
        results = new bytes[](calls.length);
        for (uint256 i = 0; i < calls.length; i++) {
            (bool success, bytes memory result) = address(this).delegatecall(calls[i]);
            require(success, "Batch call failed");
            results[i] = result;
        }
    }

    /**
     * @dev Checks if arbitrage execution would be profitable
     * @param params Arbitrage parameters
     * @return profitable Whether execution would be profitable
     * @return estimatedProfit Estimated profit amount
     */
    function isProfitable(ArbitrageParams calldata params)
        external
        view
        returns (bool profitable, uint256 estimatedProfit)
    {
        // Calculate flashloan premium
        uint256 premium = (params.flashloanAmount * AAVE_POOL.FLASHLOAN_PREMIUM_TOTAL()) / 10000;

        // Estimate gas cost (this should be more sophisticated in production)
        uint256 gasEstimate = tx.gasprice * 500000; // Assume 500k gas

        // Calculate minimum profit required
        uint256 minProfit = (params.flashloanAmount * minProfitBasisPoints) / 10000;

        // Total costs
        uint256 totalCosts = premium + gasEstimate + minProfit;

        // Check if expected output minus input exceeds costs
        if (params.minAmountOut > params.amountIn + totalCosts) {
            profitable = true;
            estimatedProfit = params.minAmountOut - params.amountIn - totalCosts;
        } else {
            profitable = false;
            estimatedProfit = 0;
        }
    }

    /**
     * @dev Gets the current flashloan premium from Aave
     * @return premium Current flashloan premium in basis points
     */
    function getFlashloanPremium() external view returns (uint256 premium) {
        premium = AAVE_POOL.FLASHLOAN_PREMIUM_TOTAL();
    }

    /**
     * @dev Checks if a token is supported and not paused
     * @param token Token address to check
     * @return supported True if token is supported
     * @return paused True if token is paused
     * @return maxSize Maximum trade size for token
     */
    function getTokenStatus(address token)
        external
        view
        returns (
            bool supported,
            bool paused,
            uint256 maxSize
        )
    {
        supported = supportedTokens[token];
        paused = tokenPaused[token];
        maxSize = maxTradeSize[token];
    }

    /**
     * @dev Returns contract configuration
     * @return config Current configuration parameters
     */
    function getConfiguration()
        external
        view
        returns (
            uint256 minProfitBasisPoints_,
            uint256 maxSlippageBasisPoints_,
            uint256 maxGasPrice_,
            uint256 ownerFeeBasisPoints_,
            address aavePool_,
            address oneinchRouter_,
            address wmatic_
        )
    {
        minProfitBasisPoints_ = minProfitBasisPoints;
        maxSlippageBasisPoints_ = maxSlippageBasisPoints;
        maxGasPrice_ = maxGasPrice;
        ownerFeeBasisPoints_ = ownerFeeBasisPoints;
        aavePool_ = address(AAVE_POOL);
        oneinchRouter_ = address(ONEINCH_ROUTER);
        wmatic_ = WMATIC;
    }

    // =============================================================================
    // UPGRADE FUNCTIONS (FOR FUTURE VERSIONS)
    // =============================================================================

    /**
     * @dev Get contract version
     * @return version Contract version string
     */
    function version() external pure returns (string memory) {
        return "1.0.0";
    }

    /**
     * @dev Implementation identifier for upgrades
     * @return impl Implementation identifier
     */
    function implementation() external pure returns (string memory impl) {
        impl = "FlashloanArbitrage_V1";
    }
}

/**
 * @title FlashloanArbitrageFactory
 * @dev Factory contract for deploying FlashloanArbitrage instances
 */
contract FlashloanArbitrageFactory {
    event ArbitrageContractDeployed(
        address indexed arbitrageContract,
        address indexed owner,
        address aavePool,
        address oneinchRouter,
        address wmatic
    );

    /**
     * @dev Deploys a new FlashloanArbitrage contract
     * @param aavePool Aave V3 Pool address
     * @param oneinchRouter 1inch Router address
     * @param wmatic WMATIC token address
     * @param initialExecutor Initial executor address
     * @return arbitrageContract Address of deployed contract
     */
    function deployArbitrageContract(
        address aavePool,
        address oneinchRouter,
        address wmatic,
        address initialExecutor
    ) external returns (address arbitrageContract) {
        arbitrageContract = address(
            new FlashloanArbitrage(
                aavePool,
                oneinchRouter,
                wmatic,
                initialExecutor
            )
        );

        // Transfer ownership to the caller
        FlashloanArbitrage(arbitrageContract).transferOwnership(msg.sender);

        emit ArbitrageContractDeployed(
            arbitrageContract,
            msg.sender,
            aavePool,
            oneinchRouter,
            wmatic
        );
    }

    /**
     * @dev Calculates the address of a contract deployed with specific parameters
     * @param aavePool Aave V3 Pool address
     * @param oneinchRouter 1inch Router address
     * @param wmatic WMATIC token address
     * @param initialExecutor Initial executor address
     * @param salt Salt for CREATE2 deployment
     * @return predicted Predicted contract address
     */
    function predictAddress(
        address aavePool,
        address oneinchRouter,
        address wmatic,
        address initialExecutor,
        bytes32 salt
    ) external view returns (address predicted) {
        bytes memory bytecode = abi.encodePacked(
            type(FlashloanArbitrage).creationCode,
            abi.encode(aavePool, oneinchRouter, wmatic, initialExecutor)
        );

        predicted = address(
            uint160(
                uint256(
                    keccak256(
                        abi.encodePacked(
                            bytes1(0xff),
                            address(this),
                            salt,
                            keccak256(bytecode)
                        )
                    )
                )
            )
        );
    }

    /**
     * @dev Deploys contract using CREATE2 for deterministic addresses
     * @param aavePool Aave V3 Pool address
     * @param oneinchRouter 1inch Router address
     * @param wmatic WMATIC token address
     * @param initialExecutor Initial executor address
     * @param salt Salt for CREATE2 deployment
     * @return arbitrageContract Address of deployed contract
     */
    function deployArbitrageContractDeterministic(
        address aavePool,
        address oneinchRouter,
        address wmatic,
        address initialExecutor,
        bytes32 salt
    ) external returns (address arbitrageContract) {
        bytes memory bytecode = abi.encodePacked(
            type(FlashloanArbitrage).creationCode,
            abi.encode(aavePool, oneinchRouter, wmatic, initialExecutor)
        );

        assembly {
            arbitrageContract := create2(0, add(bytecode, 0x20), mload(bytecode), salt)
        }

        require(arbitrageContract != address(0), "Deployment failed");

        // Transfer ownership to the caller
        FlashloanArbitrage(arbitrageContract).transferOwnership(msg.sender);

        emit ArbitrageContractDeployed(
            arbitrageContract,
            msg.sender,
            aavePool,
            oneinchRouter,
            wmatic
        );
    }
}