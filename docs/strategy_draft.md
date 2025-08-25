With my system, I will be managing lots of crypto coins.

For each Coin that I am in we can have a long position, a short position and a cash position. In hyperliquid we can't have multiple long positions for a single coin, when we buy more it just gets added to the current position and certain values are recalulated. Same for shorts.

When I open a trade, I am generally assuming that that the price is going up, but of course, I could be wrong. I am also always going to be placing orders with a coins maximum leverage. So if I order $1000 usd of LINK with 10x leverage, my margin will be $100. If I purchase $1000 of XRP at 20x, my margin will actually be $50.

Going back to the LINK example my initial_position_allocation is $100 (this is a fixed number). But since my position_allocation is meant to grow, I would have another variable current_position_allocation which would also be $100. Like I said, this controls $1000 worth of LINK.

Each token has a long allocation and hedge allocation, which starts at 50/50. However, those percentages will fluxuate as the trade strategy works its magic.



ENTER TRADE

When I enter a trade with this strategy it will all be long. I will enter a unit_size which is a dollar amount of movement I am expecting the app to listen for. current_unit is set to 0, which is the entry price hyperliquid keeps track of this for me, if I add to my position at a lower price then my entry price would be the average of my two buys. We let hyperliquid manage that. We will also start by setting peak_unit and valley_unit to 0 as well.

The app has a websocket connection to hyperliquid to listen to the current price of the coin.



ADVANCE Phase

Once we enter a trade we are in the advance phase

Whenever the price goes up a unit size we increment current_unit +1. We also increment peak_unit +1. As long as the price is going up then all we are doing is incrementing those two variables (valley_unit remained 0), as well as calculating 10% of our position value (the position value is managed by hyperliquid) which will be a variable called position_fragment.



All of this is the advance phase.



When the price drops a unit we enter the RETRACEMENT phase. For each of the these we would be decrementing the current_unit and valley_unit by 1.



When current_unit - peak unit = -1

* we sell 1 position_fragment value of our position and

* short the coin by 1 position_fragment value



When current_unit - peak unit = -2

* we sell 2 position_fragment's value of our position and

* short the coin by 1 position_fragment value



* the remaining position_fragment remains in cash



When current_unit - peak unit = -3

* we sell 2 position_fragment's value of our position and

* short the coin by 1 position_fragment value

* the remaining position_fragment remains in cash



When current_unit - peak unit = -4

* we sell 2 position_fragment's value of our position and

* short the coin by 1 position_fragment value.

* the remaining position_fragment remains in cash



When current_unit - peak unit = -5

* we sell the remaining long position for market price

* We will save a temp variable temp_cash_fragment which is how much that final amount was.



At this point 50% of our position is a short and 50% is in cash. at unit -7 we enter the DECLINE phase (This description comes later).



At any point during the retracement phase if the unit goes back up we will just do the Opposite of what we just did.



Unit change from: -6 unit --> -5 unit

* buy long temp_cash_fragment



Unit change from: -5 unit --> -4 unit

* we partially close the short position of the coin by 1 position_fragment value

* we buy long 2 position_fragment's value at market price



Unit change from: -4 unit --> -3 unit

* we partially close the short position of the coin by 1 position_fragment value

* we buy long 2 position_fragment's value at market price



Unit change from: -3 unit --> -2 unit

* we partially close the short position of the coin by 1 position_fragment value

* we buy long 2 position_fragment's value at market price



Unit change from: -2 unit --> -1 unit

* we will close the rest of the short and save that amount in temp_cash_fragment

* we will buy long temp_cash_fragment amount



Lots of fluctuation can happen, where the price goes up and down. We will likely lose a little value in this phase. and that is ok.



RESET Phase.

Its not really a phase, but it is something that happens. We are fully long, and We have not short or cash position.

* all unit variables are reset to 0

* current_position_allocation is reset to whatever our current margin is (it could be less than the initial margin but hopefully it is more)

* Advance Phase starts again



DECLINE Phase

At this point Roughly half of our position is in cash and half is in a short.

We will be as long as current_unit - valley_unit = 0 we are in the decline phase and all we do is let the short position gain in profit. if current_unit - valley_unit = 1 then we will take the current value of the short position divide by 4 and save that number as variable hedge_fragment.

If current_unit - valley_unit goes back to 0 we just continue, and if current_unit - valley_unit goes back to 1 then we just recalculate.



RECOVERY phase:

when current_unit - valley_unit = 2 we have entered the recovery phase



Unit 2 - 4

* Close 1 hedge_fragment value of short

* Buy 1 hedge_fragment value at market price

* Buy 1 position_fragment's value at market price



Unit 5

* Close remaining short and save amout as temp_hedge_value

* Buy temp_hedge_value value at market price

* Buy 1 position_fragment's value at market price



At any point the unit can go up and down so we just do the opposite. We could lose some value in recovery phase, but that is ok.



Unit 6

RESET Phase and then Back to ADVANCE.

Hopefully our current position size is larger because of the shorts.
