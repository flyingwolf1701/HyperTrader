from hyperliquid.info import Info

def check_orders():
    info = Info(False)  # testnet
    orders = info.open_orders('0x329C49392608175A071fC9AF982fF625f119fFAE')
    print('Open orders:', orders)
    
    # Get user state
    state = info.user_state('0x329C49392608175A071fC9AF982fF625f119fFAE')
    if state and 'assetPositions' in state:
        for pos in state['assetPositions']:
            if pos['position']['coin'] == 'BTC':
                print(f"BTC Position: Size={pos['position']['szi']}, Entry=${pos['position']['entryPx']}")
                break

if __name__ == "__main__":
    check_orders()