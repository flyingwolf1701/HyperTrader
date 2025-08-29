
# Main.py Notes
- it is odd that websocket is created last in main.py class hyperliquid. that was a bad choice by Claude to probably fix some other issue. It should be opened before the trade is placed. 
- main.py monitor_strategy is just a bunch of fluff that provides almost no value. Probably another stupid thing AI added as a result of something not working. I think we should just delete it and start over. Its much better to have logs closer to the code. This just abstracts things away making it difficult to debug.
- main.py run_tests... What the hell is this for? Why is Claude so against proper unit testing. It doesn't ever want to write tests for me it. it just wants to write scripts. Claude has created multiple files that start with "test_" but they are not test files they are scripts. This is stupid. You generally don't have a function in main for running tests. that is what pytest is for.
- shut down "Ask about position closure" doesn't work and it is extra complexity so should be deleted.
- Run price tracker wasn't working. I think it will need a lot of work. I want it to use UnitTracker in models.py and just track the unit and phase we are in but without an trading. It will just take the first price we get and pretend that is our entry_price.


# Models.py UnitTracker
- [I think this has already be resolved] unit_size is also a bad variable name. I tried unit_value, but that wasn't clear to me so I updated it to unit_size_usd. That shuold do the trick
- [I think this has already be resolved] self.position_fragment = Decimal("0") should be a dict. with usd and coin_value as keys.
- [I think this has already be resolved] same for self.hedge_fragment
- [I think this has already be resolved] Debouncing to prevent rapid oscillation... This was a terrible idea AI add without my approval Why on earth would I want this? it can possibly work as we cannot predict price fluxuations. How can it know if its a fluxuaiton or that the price is about to go up or down? 
- [I think this has already be resolved] calculate_unit_change is a lot of stupid ideas. and is so overly complex for a simple concept. I think this is a big reason why things are not working. 
- [I think this has already be resolved] I think we could do a sort of node data structuer here with a list called peak_unit_prices. the entry price will be posistion 0 and peak_unit_prices is the last item in the list plus unit_value. and when the current price reaches next_peak_unit_price that gets pushed onto the list. next_peak_unit_price is updated and current unit is the length of next_peak_unit_price.
- [I think this has already be resolved] we would do the same thing for next_valley_unit_price
- [I think this has already be resolved] or we can do an actual data structure that will manage this for us. Or use a dict instead of a list with the key as the unit. which I think keys can be negative numbers. then we can just call on the dict at its address with the current_unit. I think that might be the best option I just listed. 
- [I think this has already be resolved] getting rid of debounce will be a big improvement. 

# Strategy_manager.py
- hardcoding eth makes it so this is an eth trader and nothing else.         self.position_fragment_eth = Decimal("0")  # ETH amount locked at peak
- self.short_positions: List[ShortPosition] = [] # we do not do this. see the strategy document. this was a stupid idea by AI
- Peak tracking self.peak_price: Optional[Decimal] = None. is covered by the dict I wanted to use. this way we are only managing a dict and a few units, current, peak and valley. and some next prices. 
- is there double work between this calculate_position_fragment_at_peak and models?
- usd_amount: Decimal, entry_price: Decimal, this is confusing. I thought entry_price was usd_amount. but a dict would be better than variables here with entry_price_usd and entry_price_coin or entry_price_{eth}.
