import math

def round_decimals_down(number:float, decimals:int=2):
    """
    Returns a value rounded down to a specific number of decimal places.
    """
    if not isinstance(decimals, int):
        raise TypeError("decimal places must be an integer")
    elif decimals < 0:
        raise ValueError("decimal places has to be 0 or more")
    elif decimals == 0:
        return math.floor(number)
    factor = 10 ** decimals
    return math.floor(number * factor) / factor

def calculate_position(symbol: str, prev_position: float, current_price: float, sub_equity: float, forecast: float, decimals: int):
    
    print('--- Calculating Position: ---')
    # Previous Position: 0.02 BTC
    # Forecast = +1
    
    # Calculate how many of the symbol we could trade (within our equity)
    # Rounding decimals down so we don't accidentally round to a position value greater than our equity.
    new_position = round_decimals_down(sub_equity / current_price, decimals)
    print(f'Position: {new_position}')

    # Whether the forecast is +ve/-ve/0 determines whether we want a long, short, or flat position.
    if forecast < 0:
        new_position = new_position * -1
    elif forecast == 0:
        new_position = 0
    else:
        pass

    # Calculate Quantity and Side needed to get to the desired position
    position_change = new_position - prev_position
    quantity = abs(position_change)
    if position_change > 0:
        side = 'BUY'
    elif position_change < 0:
        side = 'SELL'
    else:
        side = 'NONE'

    return quantity, side, new_position

if __name__ == '__main__':
    pass