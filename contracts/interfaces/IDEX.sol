// DEX interfaces 
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title IDEX
 * @dev Universal interface for interacting with multiple DEX protocols
 * @notice Supports UniswapV2, SushiSwap, QuickSwap, and other AMM-style DEXs
 */

// =============================================================================
// UNISWAP V2 STYLE INTERFACES
// =============================================================================

/**
 * @title IUniswapV2Router
 * @dev Interface for Uniswap V2 style routers (SushiSwap, QuickSwap, etc.)
 */
interface IUniswapV2Router {
    /**
     * @dev Returns the address of the wrapped native token
     */
    function WETH() external pure returns (address);

    /**
     * @dev Returns the factory address
     */
    function factory() external pure returns (address);

    /**
     * @dev Adds liquidity to a token pair
     * @param tokenA Address of token A
     * @param tokenB Address of token B
     * @param amountADesired Desired amount of token A
     * @param amountBDesired Desired amount of token B
     * @param amountAMin Minimum amount of token A
     * @param amountBMin Minimum amount of token B
     * @param to Address to receive LP tokens
     * @param deadline Transaction deadline
     */
    function addLiquidity(
        address tokenA,
        address tokenB,
        uint256 amountADesired,
        uint256 amountBDesired,
        uint256 amountAMin,
        uint256 amountBMin,
        address to,
        uint256 deadline
    ) external returns (uint256 amountA, uint256 amountB, uint256 liquidity);

    /**
     * @dev Removes liquidity from a token pair
     * @param tokenA Address of token A
     * @param tokenB Address of token B
     * @param liquidity Amount of LP tokens to burn
     * @param amountAMin Minimum amount of token A to receive
     * @param amountBMin Minimum amount of token B to receive
     * @param to Address to receive tokens
     * @param deadline Transaction deadline
     */
    function removeLiquidity(
        address tokenA,
        address tokenB,
        uint256 liquidity,
        uint256 amountAMin,
        uint256 amountBMin,
        address to,
        uint256 deadline
    ) external returns (uint256 amountA, uint256 amountB);

    /**
     * @dev Swaps exact tokens for tokens
     * @param amountIn Exact amount of input tokens
     * @param amountOutMin Minimum amount of output tokens
     * @param path Array of token addresses representing the swap path
     * @param to Address to receive output tokens
     * @param deadline Transaction deadline
     */
    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);

    /**
     * @dev Swaps tokens for exact tokens
     * @param amountOut Exact amount of output tokens desired
     * @param amountInMax Maximum amount of input tokens
     * @param path Array of token addresses representing the swap path
     * @param to Address to receive output tokens
     * @param deadline Transaction deadline
     */
    function swapTokensForExactTokens(
        uint256 amountOut,
        uint256 amountInMax,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);

    /**
     * @dev Swaps exact ETH for tokens
     * @param amountOutMin Minimum amount of output tokens
     * @param path Array of token addresses (starting with WETH)
     * @param to Address to receive output tokens
     * @param deadline Transaction deadline
     */
    function swapExactETHForTokens(
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external payable returns (uint256[] memory amounts);

    /**
     * @dev Swaps exact tokens for ETH
     * @param amountIn Exact amount of input tokens
     * @param amountOutMin Minimum amount of ETH to receive
     * @param path Array of token addresses (ending with WETH)
     * @param to Address to receive ETH
     * @param deadline Transaction deadline
     */
    function swapExactTokensForETH(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);

    /**
     * @dev Gets amounts out for exact amount in
     * @param amountIn Input amount
     * @param path Swap path
     * @return amounts Array of output amounts for each step
     */
    function getAmountsOut(uint256 amountIn, address[] calldata path)
        external
        view
        returns (uint256[] memory amounts);

    /**
     * @dev Gets amounts in for exact amount out
     * @param amountOut Output amount
     * @param path Swap path
     * @return amounts Array of input amounts for each step
     */
    function getAmountsIn(uint256 amountOut, address[] calldata path)
        external
        view
        returns (uint256[] memory amounts);

    /**
     * @dev Quotes amount out for amount in
     * @param amountA Amount of token A
     * @param reserveA Reserve of token A
     * @param reserveB Reserve of token B
     * @return amountB Equivalent amount of token B
     */
    function quote(
        uint256 amountA,
        uint256 reserveA,
        uint256 reserveB
    ) external pure returns (uint256 amountB);

    /**
     * @dev Gets amount out for exact amount in accounting for fees
     * @param amountIn Input amount
     * @param reserveIn Input token reserve
     * @param reserveOut Output token reserve
     * @return amountOut Output amount
     */
    function getAmountOut(
        uint256 amountIn,
        uint256 reserveIn,
        uint256 reserveOut
    ) external pure returns (uint256 amountOut);

    /**
     * @dev Gets amount in for exact amount out accounting for fees
     * @param amountOut Output amount
     * @param reserveIn Input token reserve
     * @param reserveOut Output token reserve
     * @return amountIn Input amount required
     */
    function getAmountIn(
        uint256 amountOut,
        uint256 reserveIn,
        uint256 reserveOut
    ) external pure returns (uint256 amountIn);
}

/**
 * @title IUniswapV2Factory
 * @dev Interface for Uniswap V2 style factories
 */
interface IUniswapV2Factory {
    /**
     * @dev Gets the pair address for two tokens
     * @param tokenA Address of token A
     * @param tokenB Address of token B
     * @return pair Pair address (or address(0) if doesn't exist)
     */
    function getPair(address tokenA, address tokenB) external view returns (address pair);

    /**
     * @dev Creates a new pair for two tokens
     * @param tokenA Address of token A
     * @param tokenB Address of token B
     * @return pair Address of the created pair
     */
    function createPair(address tokenA, address tokenB) external returns (address pair);

    /**
     * @dev Returns the total number of pairs
     */
    function allPairsLength() external view returns (uint256);

    /**
     * @dev Returns pair address at index
     * @param index Pair index
     * @return pair Pair address
     */
    function allPairs(uint256 index) external view returns (address pair);

    /**
     * @dev Returns the fee recipient
     */
    function feeTo() external view returns (address);

    /**
     * @dev Returns the fee setter
     */
    function feeToSetter() external view returns (address);
}

/**
 * @title IUniswapV2Pair
 * @dev Interface for Uniswap V2 style pairs
 */
interface IUniswapV2Pair {
    /**
     * @dev Returns the reserves and last update timestamp
     * @return reserve0 Reserve of token0
     * @return reserve1 Reserve of token1
     * @return blockTimestampLast Last update timestamp
     */
    function getReserves()
        external
        view
        returns (
            uint112 reserve0,
            uint112 reserve1,
            uint32 blockTimestampLast
        );

    /**
     * @dev Returns token0 address
     */
    function token0() external view returns (address);

    /**
     * @dev Returns token1 address
     */
    function token1() external view returns (address);

    /**
     * @dev Returns the current price cumulative values
     */
    function price0CumulativeLast() external view returns (uint256);
    function price1CumulativeLast() external view returns (uint256);

    /**
     * @dev Swaps tokens
     * @param amount0Out Amount of token0 to receive
     * @param amount1Out Amount of token1 to receive
     * @param to Address to receive tokens
     * @param data Callback data
     */
    function swap(
        uint256 amount0Out,
        uint256 amount1Out,
        address to,
        bytes calldata data
    ) external;

    /**
     * @dev Syncs reserves to match balances
     */
    function sync() external;

    /**
     * @dev Event emitted on swaps
     */
    event Swap(
        address indexed sender,
        uint256 amount0In,
        uint256 amount1In,
        uint256 amount0Out,
        uint256 amount1Out,
        address indexed to
    );

    /**
     * @dev Event emitted when reserves are synced
     */
    event Sync(uint112 reserve0, uint112 reserve1);
}

// =============================================================================
// CURVE STYLE INTERFACES
// =============================================================================

/**
 *