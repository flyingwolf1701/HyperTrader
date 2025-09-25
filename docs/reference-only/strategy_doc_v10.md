Long-Biased Grid Trading Strategy v10.0.0
1. Core Philosophy
This is a bull-market thesis strategy engineered to capitalize on price volatility while maintaining a long-term upward bias. The ultimate goal is to accumulate a position at the lowest possible price by systematically taking profits during price retracements and compounding returns during recoveries.

The strategy is centered around a dynamic grid system that continuously maintains four active orders trailing the current price. This "sliding window" approach allows for fully automated, seamless execution in both trending and ranging markets without manual intervention.

2. User Initialization and Setup
Required User Inputs
Before activation, the user must define the following parameters:

Wallet Allocation: The total USD amount to be dedicated to this strategy.

Leverage Setting: The leverage multiplier to be applied to the allocation (e.g., 10x).

Asset Selection: The specific coin/token to be traded (e.g., ETH, BTC, SOL).

Unit Size: The price movement increment that defines one "unit." This can be a fixed dollar amount (e.g., $100 for BTC, $1 for SOL) or a percentage.

Fragment Calculation
The total leveraged position is divided into four equal parts, or "fragments."

Position Fragment: Each fragment represents 25% of the total position.

Sell Fragments: Sells are executed based on a fixed amount of the coin (e.g., selling 0.1 ETH). This ensures a consistent reduction of the asset position regardless of price.

Buy Fragments: Buys are executed based on a fixed USD amount (e.g., buying $2,500 worth of ETH). This ensures consistent capital deployment.

3. Initial Order Placement
The strategy begins with a full position in the selected asset.

Establish Position: A market buy is executed for the full Wallet Allocation multiplied by the Leverage Setting.

Set Anchor Price: The execution price of the initial buy order is recorded and established as current_unit = 0.

Place Initial Grid: The system immediately places four stop-loss sell orders, each for a 25% position fragment. These are placed at prices corresponding to:

current_unit - 1

current_unit - 2

current_unit - 3

current_unit - 4

At this point, the strategy is fully active and the automated grid management begins.

4. Core Logic: The Dynamic 4-Order Grid
The strategy's foundation is a simple but powerful set of rules governing a constantly maintained grid of four orders. The composition of these orders (sells vs. buys) determines the system's state and response to market movements.

The Fundamental Rule
The system must maintain exactly four active orders at all times.

Dynamic Order Replacement
The grid fluidly adapts to price action through an immediate replacement mechanism.

When a stop-loss sell order is triggered, the system assumes it is filled and immediately places a new stop-entry buy order at current_unit + 1.

When a stop-entry buy order is triggered, the system assumes it is filled and immediately places a new stop-loss sell order at current_unit - 1.

Note: Trailing buy orders are created using Hyperliquid's stop-loss mechanism, which allows them to function as stop-entry orders.

Portfolio State Examples
This section illustrates the portfolio's composition as price movements trigger orders. (Assumes a $10,000 initial position).

State Description	Position (Asset / Cash)	Sell Orders Active	Buy Orders Active
Full Position	$10,000 / $0	4	0
(Price drops, 1 sell triggers)			
75% Position	$7,500 / $2,500	3	1
(Price drops, 1 more sell triggers)			
50% Position	$5,000 / $5,000	2	2
(Price drops, 1 more sell triggers)			
25% Position	$2,500 / $7,500	1	3
(Price drops, final sell triggers)			
Full Cash Position	$0 / $10,000	0	4
As buy orders are triggered during a price recovery, this process reverses, seamlessly scaling the portfolio back into the asset.

Grid Sliding in Trending Markets
When the price trends strongly in one direction without triggering orders, the entire 4-order grid "slides" to follow the price.

Price Advancing (Trending Up): While in a 100% position, as current_unit increases, the grid of four sell orders moves up. The bot adds a new sell order at current_unit - 1 and cancels the oldest sell order at current_unit - 5. This maintains the grid one unit behind the current price.

Price Declining (Trending Down): While in a 100% cash position, as current_unit decreases, the grid of four buy orders moves down. The bot adds a new buy order at current_unit + 1 and cancels the oldest buy order at current_unit + 5. This maintains the grid one unit ahead of the current price.

5. Compounding Growth Mechanism
The strategy is designed to compound returns organically by reinvesting realized profits.

Track Realized PnL: Every time a sell order is executed for a profit, that profit is tracked in a current_realized_pnl variable.

Reinvest Profits: When the system is in a state of recovery (i.e., it has cash on hand and is executing buy orders), the accumulated current_realized_pnl is used to increase the size of the buy fragments.

Dynamic Recalculation: The current_realized_pnl is divided by the number of active buy orders and added to the USD size of each buy fragment. This ensures that profits are automatically redeployed to acquire a larger position over time, achieving a continuous compounding effect.

6. Implementation and Risk
State Detection: The system's current state is determined entirely by the composition of the four active orders (e.g., 4 sells = Full Position, 2 sells/2 buys = 50% Position).

Execution: The bot relies on real-time WebSocket notifications of order fills to trigger the immediate placement of replacement orders.

Resilience: On startup or reconnection, the system should query all open orders to reconstruct the current grid state and resume normal operation.