1. User places an order, such as:
```bash
cd backend
uv run python src/main.py --symbol SOL --wallet long --unit-size 0.5 --position-size 2000 --leverage 20 --testnet
uv run python src/main.py --symbol BTC --wallet long --unit-size 5 --position-size 20000 --leverage 40 --testnet
uv run python src/main.py --symbol ETH --wallet long --unit-size 1 --position-size 12500 --leverage 25 --testnet
```
Currently this is a long order at market price (there may be more options in the future).
2. System places the order and waits for the response message that the order has been filled.
3. The response message should contain the `entry_price`, which the system will use to build the initial `position_map`.
    - The `position_map` is a dictionary with the following structure:
    ```python
        position_map = {
            unit_number: {
                price: entry_price + (unit_size*unit_number)
                order_id: [], # This needs to be a list because multiple orders can and will be placed at each order position. But there there will only be one active order at a time.
                order status: [], # We will only be concerned with the last item in these lists. The rest is just there for storage.
                # I believe there is more to this dictionary, but it is all I remember off the top of my head
            }
        }
    ```
    - This map will be used for the duration of the trade. The reset phase may not really matter. Our position_size will grow over time but we will just be building on this `position_map`
    4. We will be maintaining two lists:
        - `trailing_stop = []`
        - `trailing_buy = []`
        - if `trailing_stop.length = 4` then we are in the advance phase
        - if `trailing_buy.length = 4` then we are in the decline phase
        - if the two lengths are another number less than 4 then we are in either retracement or recovery
        - if the last phase was decline, then it is recovery, other wise it is retracement.
        - Recovery phase is where we start reinvesting our pnl. we increase our fragments by the pnl divided by 4
        - This makes it so we no longer need a reset phase.
        - truth be told, phase names don't matter much, they are mostly for documentation and logging, to make communication easier.
    5. After the initial `entry_price` has been returned and the initial `position_map` built we start creating our initial positions.
        - on initiation, `current_unit = 0`
        - at `current_unit - 1` we will check `position_map[current_unit - 1].price` and place our first stop loss order to sell at that price.
        - then we will save the `order_id` and `order_status` to `position_map[unit_number].order_id` and `position_map[unit_number].order_status`by appending them to the end of the lists.
        - repeat for -2, -3, and -4
        - Actually current code starts placing -4 so we can append to the end of the list. tht is more effiecient.
        - `trailing_stop = [-4, -3, -2, -1]`
    6. At this point we have completed the initial order and set up.
    7. Price goes up (advance phase):
        - Meanwhile we have our websocket client listening for the `current_price` of the coin.
        - If the `current_price is >= position_map[current_unit + 1].price`.
            a. `current_unit += 1`
            b. place a new stoploss order for `current_unit - 1` for `position_map[current_unit - 1].price`
            c. update `order_id` and `order_status` for `position_map[current_unit - 1]`
            d. update trailing_stop by appending to the end of the list: `trailing_stop = [-4, -3, -2, -1, 0]`
            e. Pop[0] from trailing_stop temporarily store as `update_order_unit`: `trailing_stop = [-3, -2, -1, 0]`
            f. cancel the stoploss order for `position_map[update_order_unit].price`
            g. update `order_status` for `position_map[update_order_unit].order_status` by updating the last item in the list.
            h. this repeats every time a unit advances
    8. Price goes down (retracement phase):
        - example `current_unit = 1` down to `current_unit = 0`:
            - `trailing_stop = [-3, -2, -1, 0]`
            - `trailing_buy = []`
        - `current_unit -= 1`
        - presumably the stoploss sell order at `current_unit - 1` is triggered.
        - We do check to see if it actually was triggered, but be do not wait for confirmation. We simply trust that it works.
        - We will immediately place our first `trailing_buy` order for `current_unit + 1` at `position_map[current_unit + 1].price`
        - then we update order_id and order_status for `position_map[current_unit + 1]`
        - update trailing_buy by appending to the end of the list: `trailing_buy = [1]`
        - Pop[-1] from trailing_stop temporarily store as `update_order_unit`: `trailing_buy = [0]`
        - update `order_status` for `position_map[update_order_unit].order_status`
            - `trailing_stop = [-3, -2, -1]`
            - `trailing_buy = [1]`
        - This could continue until:
            - `trailing_stop = []`
            - `trailing_buy = [ -2, -1, 0, 1]`
            - At which point we enter the decline phase.
    9. Price goes up (retracement phase):
        - example `current_unit = 0` up to `current_unit = 1`:
            - `trailing_stop = [-3, -2, -1]`
            - `trailing_buy = [1]`
        - presumably the stoploss buy order at `current_unit + 1` is triggered.
        - we do not wait for confirmation. We simply trust that it works.
        - then we place a new `trailing_stop` order for `current_unit - 1`
        - We update our `position_map` and append `trailing_buy`
            - `trailing_stop = [-3, -2, -1, 0]`
            - `trailing_buy = []`
    10. Price goes down (decline phase):
        - example `current_unit = -2` down to `current_unit = -3`:
            - `trailing_stop = []`
            - `trailing_buy = [-2, -1, 0, 1]`
        - `current_unit -= 1`
        - append[0] current_unit to `trailing_buy`
        - create stop loss buy order for `position_map[current_unit + 1].price`
        - update `order_id` and `order_status` for `position_map[current_unit + 1]`
        - pop[-1] from `trailing_buy`
            - `trailing_stop = []`
            - `trailing_buy = [-3,-2, -1, 0]`
    11. Price goes up (recovery phase):
        - example `current_unit = -3` up to `current_unit = -2`:
            - `trailing_stop = []`
            - `trailing_buy = [-2, -1, 0, 1]`
        - `current_unit += 1`
        - order at `trailing_buy` is triggered.
        - place a new `trailing_stop` order for `current_unit - 1`
        - update `order_status` for `position_map[current_unit = -1]`
        - pop[0] from `trailing_buy` and temporarily store as `update_order_unit`
        - update `order_id` and `order_status` for `position_map[update_order_unit]`
    Notes:
    - when we buy and sell we are selling a fragment still
    - we don't really need a reset phase anymore
    - when we sell we track `current_realized_pnl`.
    - Some we have to reinvest `current_realized_pnl`
    - We will divide `current_realized_pnl` by 4 then add (or subrtract) that number to our fragments for when we start purchacing in the recover phase.
I suspect that the code is significanltly more complex that this and does all of these things in weird ineffiecient ways.
Please clean up the code based on this document of how it should work.
DO NOT Save code for backwards compataility, that becomes zombie junk code that makes the code base hard to read and debug. Please clean up zombie code as you come accross it.
