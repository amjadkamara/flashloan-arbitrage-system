// 1inch router interface 
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title I1InchRouter
 * @dev Interface for 1inch Router V5 on Polygon
 * @notice This interface defines the essential functions for token swapping via 1inch
 */
interface I1InchRouter {
    /**
     * @dev Struct containing swap description parameters
     * @param srcToken Source token address
     * @param dstToken Destination token address
     * @param srcReceiver Address that will receive leftover source tokens
     * @param dstReceiver Address that will receive destination tokens
     * @param amount Amount of source tokens to swap
     * @param minReturnAmount Minimum amount of destination tokens expected
     * @param flags Additional flags for swap customization
     */
    struct SwapDescription {
        IERC20 srcToken;
        IERC20 dstToken;
        address payable srcReceiver;
        address payable dstReceiver;
        uint256 amount;
        uint256 minReturnAmount;
        uint256 flags;
    }

    /**
     * @dev Performs a token swap with arbitrary data
     * @param executor Address that will execute the swap
     * @param desc Swap description containing swap parameters
     * @param permit Permit signature data (if applicable)
     * @param data Arbitrary data for the swap execution
     * @return returnAmount The actual amount of destination tokens received
     * @return spentAmount The actual amount of source tokens spent
     */
    function swap(
        address executor,
        SwapDescription calldata desc,
        bytes calldata permit,
        bytes calldata data
    ) external payable returns (uint256 returnAmount, uint256 spentAmount);

    /**
     * @dev Performs an unlimited swap where entire source token balance is used
     * @param executor Address that will execute the swap
     * @param desc Swap description containing swap parameters
     * @param permit Permit signature data (if applicable)
     * @param data Arbitrary data for the swap execution
     * @return returnAmount The actual amount of destination tokens received
     * @return spentAmount The actual amount of source tokens spent
     */
    function unoswap(
        address executor,
        SwapDescription calldata desc,
        bytes calldata permit,
        bytes calldata data
    ) external payable returns (uint256 returnAmount, uint256 spentAmount);

    /**
     * @dev Performs a simple token-to-token swap without complex routing
     * @param srcToken Source token address
     * @param amount Amount of source tokens to swap
     * @param minReturn Minimum amount of destination tokens expected
     * @param pools Array of pool addresses for the swap route
     * @return returnAmount The actual amount of destination tokens received
     */
    function unoswapTo(
        IERC20 srcToken,
        uint256 amount,
        uint256 minReturn,
        bytes32[] calldata pools
    ) external payable returns (uint256 returnAmount);

    /**
     * @dev Performs a multi-hop swap with specified destinations
     * @param srcToken Source token address
     * @param amount Amount of source tokens to swap
     * @param minReturn Minimum amount of destination tokens expected
     * @param pools Array of pool identifiers for the swap route
     * @param dstReceiver Address that will receive destination tokens
     * @return returnAmount The actual amount of destination tokens received
     */
    function unoswapTo2(
        IERC20 srcToken,
        uint256 amount,
        uint256 minReturn,
        bytes32[] calldata pools,
        address payable dstReceiver
    ) external payable returns (uint256 returnAmount);

    /**
     * @dev Discounted swap for partners (if applicable)
     * @param caller Address initiating the swap
     * @param desc Swap description containing swap parameters
     * @param permit Permit signature data (if applicable)
     * @param data Arbitrary data for the swap execution
     * @return returnAmount The actual amount of destination tokens received
     * @return spentAmount The actual amount of source tokens spent
     */
    function discountedSwap(
        address caller,
        SwapDescription calldata desc,
        bytes calldata permit,
        bytes calldata data
    ) external payable returns (uint256 returnAmount, uint256 spentAmount);

    /**
     * @dev Gets the expected return amount for a potential swap
     * @param srcToken Source token address
     * @param dstToken Destination token address
     * @param amount Amount of source tokens
     * @return returnAmount Expected destination token amount
     * @return distribution Array showing distribution across different DEXs
     */
    function getExpectedReturn(
        IERC20 srcToken,
        IERC20 dstToken,
        uint256 amount
    ) external view returns (uint256 returnAmount, uint256[] memory distribution);

    /**
     * @dev Gets expected return with gas estimation
     * @param srcToken Source token address
     * @param dstToken Destination token address
     * @param amount Amount of source tokens
     * @param parts Number of parts to split the trade
     * @param flags Additional flags
     * @return returnAmount Expected destination token amount
     * @return estimateGasAmount Estimated gas cost
     * @return distribution Array showing distribution across different DEXs
     */
    function getExpectedReturnWithGas(
        IERC20 srcToken,
        IERC20 dstToken,
        uint256 amount,
        uint256 parts,
        uint256 flags
    )
        external
        view
        returns (
            uint256 returnAmount,
            uint256 estimateGasAmount,
            uint256[] memory distribution
        );

    /**
     * @dev Checks if an order is valid and fillable
     * @param order Order data
     * @param signature Order signature
     * @param orderHash Hash of the order
     * @return isValid True if order is valid
     */
    function isValidSignature(
        bytes calldata order,
        bytes calldata signature,
        bytes32 orderHash
    ) external view returns (bool isValid);

    /**
     * @dev Returns the address of the wrapped native token (WMATIC on Polygon)
     * @return Address of wrapped native token
     */
    function WETH() external view returns (address);

    /**
     * @dev Event emitted when a swap is executed
     * @param sender Address that initiated the swap
     * @param srcToken Source token address
     * @param dstToken Destination token address
     * @param dstReceiver Address that received destination tokens
     * @param spentAmount Amount of source tokens spent
     * @param returnAmount Amount of destination tokens received
     */
    event Swapped(
        address indexed sender,
        IERC20 indexed srcToken,
        IERC20 indexed dstToken,
        address dstReceiver,
        uint256 spentAmount,
        uint256 returnAmount
    );

    /**
     * @dev Event emitted when an order is filled
     * @param orderHash Hash of the filled order
     * @param remainingAmount Remaining amount after partial fill
     */
    event OrderFilled(bytes32 indexed orderHash, uint256 remainingAmount);

    /**
     * @dev Event emitted when an order is cancelled
     * @param orderHash Hash of the cancelled order
     */
    event OrderCancelled(bytes32 indexed orderHash);
}

/**
 * @title I1InchAggregationExecutor
 * @dev Interface for 1inch aggregation executor
 */
interface I1InchAggregationExecutor {
    /**
     * @dev Executes calls to multiple targets
     * @param targets Array of target addresses
     * @param data Array of call data
     * @return results Array of call results
     */
    function executeCalls(address[] calldata targets, bytes[] calldata data)
        external
        returns (bytes[] memory results);
}

/**
 * @title I1InchCalldataDecoder
 * @dev Interface for decoding 1inch calldata
 */
interface I1InchCalldataDecoder {
    /**
     * @dev Decodes swap calldata to extract swap parameters
     * @param data Encoded swap calldata
     * @return srcToken Source token address
     * @return dstToken Destination token address
     * @return srcReceiver Address receiving leftover source tokens
     * @return dstReceiver Address receiving destination tokens
     * @return amount Amount of source tokens
     * @return minReturnAmount Minimum expected destination amount
     * @return flags Swap flags
     */
    function decodeSwapCalldata(bytes calldata data)
        external
        pure
        returns (
            address srcToken,
            address dstToken,
            address srcReceiver,
            address dstReceiver,
            uint256 amount,
            uint256 minReturnAmount,
            uint256 flags
        );
}