// Aave pool interface 
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title IAavePool
 * @dev Interface for Aave V3 Pool contract on Polygon
 * @notice This interface defines the essential functions needed for flashloan operations
 */
interface IAavePool {
    /**
     * @dev Struct to define flashloan parameters
     * @param asset The address of the asset being flash borrowed
     * @param amount The amount of the asset being flash borrowed
     * @param premium The fee amount for the flashloan
     * @param initiator The address that initiated the flashloan
     * @param params Additional parameters encoded as bytes
     */
    struct FlashLoanParams {
        address asset;
        uint256 amount;
        uint256 premium;
        address initiator;
        bytes params;
    }

    /**
     * @dev Initiates a flashloan
     * @param receiverAddress The address of the contract receiving the funds
     * @param assets Array of asset addresses to be flash borrowed
     * @param amounts Array of amounts to be flash borrowed
     * @param interestRateModes Array of interest rate modes (0 = none, 1 = stable, 2 = variable)
     * @param onBehalfOf The address that will receive the debt (usually the same as receiverAddress)
     * @param params Additional parameters as bytes
     * @param referralCode Referral code for the flashloan (can be 0)
     */
    function flashLoan(
        address receiverAddress,
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata interestRateModes,
        address onBehalfOf,
        bytes calldata params,
        uint16 referralCode
    ) external;

    /**
     * @dev Returns the normalized income of the reserve
     * @param asset The address of the underlying asset of the reserve
     * @return The reserve's normalized income
     */
    function getReserveNormalizedIncome(address asset) external view returns (uint256);

    /**
     * @dev Returns the normalized variable debt per unit of asset
     * @param asset The address of the underlying asset of the reserve
     * @return The reserve normalized variable debt
     */
    function getReserveNormalizedVariableDebt(address asset) external view returns (uint256);

    /**
     * @dev Returns the configuration of the reserve
     * @param asset The address of the underlying asset of the reserve
     * @return The configuration data
     */
    function getConfiguration(address asset) external view returns (uint256);

    /**
     * @dev Returns the reserve data
     * @param asset The address of the underlying asset
     * @return configuration The configuration data
     * @return liquidityIndex The liquidity index
     * @return currentLiquidityRate The current liquidity rate
     * @return variableBorrowIndex The variable borrow index
     * @return currentVariableBorrowRate The current variable borrow rate
     * @return currentStableBorrowRate The current stable borrow rate
     * @return lastUpdateTimestamp The timestamp of the last update
     * @return id The id of the reserve
     * @return aTokenAddress The address of the aToken
     * @return stableDebtTokenAddress The address of the stable debt token
     * @return variableDebtTokenAddress The address of the variable debt token
     * @return interestRateStrategyAddress The address of the interest rate strategy
     * @return accruedToTreasury The accrued to treasury amount
     * @return unbacked The unbacked amount
     * @return isolationModeTotalDebt The isolation mode total debt
     */
    function getReserveData(address asset)
        external
        view
        returns (
            uint256 configuration,
            uint128 liquidityIndex,
            uint128 currentLiquidityRate,
            uint128 variableBorrowIndex,
            uint128 currentVariableBorrowRate,
            uint128 currentStableBorrowRate,
            uint40 lastUpdateTimestamp,
            uint16 id,
            address aTokenAddress,
            address stableDebtTokenAddress,
            address variableDebtTokenAddress,
            address interestRateStrategyAddress,
            uint128 accruedToTreasury,
            uint128 unbacked,
            uint128 isolationModeTotalDebt
        );

    /**
     * @dev Returns the list of initialized reserves
     * @return The list of initialized reserves
     */
    function getReservesList() external view returns (address[] memory);

    /**
     * @dev Returns the address of the Aave PoolAddressesProvider
     * @return The address of the PoolAddressesProvider
     */
    function ADDRESSES_PROVIDER() external view returns (address);

    /**
     * @dev Returns the flashloan premium total (in basis points)
     * @return The flashloan premium total
     */
    function FLASHLOAN_PREMIUM_TOTAL() external view returns (uint128);

    /**
     * @dev Returns the flashloan premium to protocol (in basis points)
     * @return The flashloan premium to protocol
     */
    function FLASHLOAN_PREMIUM_TO_PROTOCOL() external view returns (uint128);

    /**
     * @dev Returns the maximum number of reserves supported
     * @return The maximum number of reserves
     */
    function MAX_NUMBER_RESERVES() external view returns (uint16);

    /**
     * @dev Returns the revision number of the contract
     * @return The revision number
     */
    function POOL_REVISION() external view returns (uint256);

    /**
     * @dev Supplies an asset to the protocol
     * @param asset The address of the underlying asset to supply
     * @param amount The amount to be supplied
     * @param onBehalfOf The address that will receive the aTokens
     * @param referralCode Referral code for the supply transaction
     */
    function supply(
        address asset,
        uint256 amount,
        address onBehalfOf,
        uint16 referralCode
    ) external;

    /**
     * @dev Withdraws an asset from the protocol
     * @param asset The address of the underlying asset to withdraw
     * @param amount The amount to withdraw (use type(uint256).max for max)
     * @param to The address that will receive the underlying asset
     * @return The final withdrawn amount
     */
    function withdraw(
        address asset,
        uint256 amount,
        address to
    ) external returns (uint256);

    /**
     * @dev Borrows an asset from the protocol
     * @param asset The address of the underlying asset to borrow
     * @param amount The amount to borrow
     * @param interestRateMode The interest rate mode (1 = stable, 2 = variable)
     * @param referralCode Referral code for the borrow transaction
     * @param onBehalfOf The address that will receive the debt
     */
    function borrow(
        address asset,
        uint256 amount,
        uint256 interestRateMode,
        uint16 referralCode,
        address onBehalfOf
    ) external;

    /**
     * @dev Repays a borrowed asset
     * @param asset The address of the borrowed underlying asset
     * @param amount The amount to repay (use type(uint256).max for max)
     * @param interestRateMode The interest rate mode (1 = stable, 2 = variable)
     * @param onBehalfOf The address for which the debt will be repaid
     * @return The final repaid amount
     */
    function repay(
        address asset,
        uint256 amount,
        uint256 interestRateMode,
        address onBehalfOf
    ) external returns (uint256);

    /**
     * @dev Returns the user account data across all reserves
     * @param user The address of the user
     * @return totalCollateralBase The total collateral of the user in the base currency
     * @return totalDebtBase The total debt of the user in the base currency
     * @return availableBorrowsBase The borrowing power left of the user in the base currency
     * @return currentLiquidationThreshold The liquidation threshold of the user
     * @return ltv The loan to value of the user
     * @return healthFactor The current health factor of the user
     */
    function getUserAccountData(address user)
        external
        view
        returns (
            uint256 totalCollateralBase,
            uint256 totalDebtBase,
            uint256 availableBorrowsBase,
            uint256 currentLiquidationThreshold,
            uint256 ltv,
            uint256 healthFactor
        );

    /**
     * @dev Event emitted when a flashloan is executed
     * @param target The address of the flashloan receiver contract
     * @param initiator The address that initiated the flashloan
     * @param asset The address of the asset being flash borrowed
     * @param amount The amount flash borrowed
     * @param interestRateMode The flashloan mode (0 for no open debt)
     * @param premium The fee flash borrowed
     * @param referralCode The referral code used
     */
    event FlashLoan(
        address indexed target,
        address indexed initiator,
        address indexed asset,
        uint256 amount,
        uint256 interestRateMode,
        uint256 premium,
        uint16 referralCode
    );

    /**
     * @dev Event emitted when assets are supplied to the protocol
     * @param reserve The address of the underlying asset of the reserve
     * @param user The address initiating the supply
     * @param onBehalfOf The address that will receive the aTokens
     * @param amount The amount supplied
     * @param referralCode The referral code used
     */
    event Supply(
        address indexed reserve,
        address user,
        address indexed onBehalfOf,
        uint256 amount,
        uint16 indexed referralCode
    );

    /**
     * @dev Event emitted when assets are withdrawn from the protocol
     * @param reserve The address of the underlying asset of the reserve
     * @param user The address initiating the withdrawal
     * @param to The address that will receive the underlying asset
     * @param amount The amount withdrawn
     */
    event Withdraw(address indexed reserve, address indexed user, address indexed to, uint256 amount);

    /**
     * @dev Event emitted when assets are borrowed from the protocol
     * @param reserve The address of the underlying asset of the reserve
     * @param user The address of the user who received the borrowed underlying asset
     * @param onBehalfOf The address that will be getting the debt
     * @param amount The amount borrowed
     * @param interestRateMode The rate mode (1 = stable, 2 = variable)
     * @param borrowRate The numeric rate at which the user has borrowed
     * @param referralCode The referral code used
     */
    event Borrow(
        address indexed reserve,
        address user,
        address indexed onBehalfOf,
        uint256 amount,
        uint256 interestRateMode,
        uint256 borrowRate,
        uint16 indexed referralCode
    );

    /**
     * @dev Event emitted when borrowed assets are repaid
     * @param reserve The address of the underlying asset of the reserve
     * @param user The address of the borrower
     * @param repayer The address of the user who repaid
     * @param amount The amount repaid
     * @param useATokens True if the repayment is done using aTokens
     */
    event Repay(
        address indexed reserve,
        address indexed user,
        address indexed repayer,
        uint256 amount,
        bool useATokens
    );
}