import json
import math
import pathlib
import os
from datetime import date, timedelta
from configparser import ConfigParser
from decimal import Decimal
from pprint import pprint

from binance.client import Client
from forex_python.converter import CurrencyCodes, CurrencyRates
from decouple import config

import telegram_bot as tg
import subsystems
from database import connect
from position_size import calculate_position, round_decimals_down

cc = CurrencyCodes()
cr = CurrencyRates()

def binanceOrder(client, side, quantity, symbol, order_type='MARKET'):
    try:
        print(f"Order: {symbol} – {side} {quantity} {symbol}")
        if os.getenv('TRADING_MODE', 'paper') == 'live':
            print('Trading Mode: Live')
            binanceOrder = client.futures_create_order(symbol=symbol, side=side, type=order_type, quantity=quantity)
        else:
            print('Trading Mode: Test')
            binanceOrder = client.create_test_order(symbol=symbol, side=side, type=order_type, quantity=quantity)
        print(f'Binance Order Response: {binanceOrder}')
    except Exception as e:
        print(f"Binance Order Response: Exception occurred - {e}")
        tg.outbound(f"Binance Order Response: Exception occurred - {e}")
        return False
    return binanceOrder

def main():
    symbol = 'BTCUSDT'

    if os.getenv('TRADING_MODE') == 'live':
        trading_mode = 'Live'
    else:
        trading_mode = 'Paper'

    # Binance Connect
    client = Client(config('BI_API_KEY'), config('BI_API_SECRET'), tld='com')

    print('--- Initial Info: ---')

    # Subsystem Info
    try:
        sub = next(item for item in subsystems.db if item['symbol'] == symbol)
    except:
        print(f'Error: {symbol} can not be found in subsystems.py')
        tg.outbound(f'⚠️ *Warning: {symbol} was not found in subsystems info!*')

    # Currency Symbol
    sub_currency = sub['currency']
    if sub_currency == 'USD' or sub_currency == 'USDT':
        sub_sign = '$'
    else:
        sub_sign = cc.get_symbol(sub_currency)

    # FX Rate
    if sub_currency == 'USDT':
        fx = 1
        print('Currency is USDT - FX Rate = 1')
    elif sub_currency != 'USDT':
        fx = cr.get_rate('USD', sub_currency)
        print(f'USD{sub_currency} FX Rate: {fx}')
    else:
        print('Error with FX Rate')

    # Binance Equity - in USD
    binance_equity = float(client.futures_account()['totalMarginBalance'])
    print(f'Binance Equity: ${binance_equity}')

    # Subsystem Equity
    sub_equity = round_decimals_down((binance_equity * sub["broker-weight"] * fx), 2)
    print(f'Subsystem Equity: {sub_sign}{sub_equity}')

    # BTC Position
    positions = client.futures_position_information()
    BTC_position = float(next(item for item in positions if item["symbol"] == 'BTCUSDT')['positionAmt'])
    prev_position = BTC_position
    print(f'BTC Balance: {BTC_position:.2f}')

    # BTC Price
    price_info = client.futures_mark_price()
    BTC_price = float(next(item for item in price_info if item['symbol'] == symbol)['markPrice'])
    print(f'BTC Current Price: {BTC_price:.2f}')

    # Forecast from Database
    connection, cursor = connect()
    cursor.execute(f"""
        SELECT date, close, forecast
        FROM {symbol}
        ORDER BY date DESC
        LIMIT 1
        """)
    rows = cursor.fetchall()
    
    record_date, record_close, forecast = rows[0]['date'], rows[0]['close'], rows[0]['forecast']
    print('--- Database Data: ---')
    print(f'Record Date: {record_date}')
    print(f'Close: {record_close}')
    print(f'Forecast: {forecast}')

    yesterday = date.strftime(date.today() - timedelta(days=1), '%Y-%m-%d')

    # Check DB date vs yesterday's date
    if record_date != yesterday:
        print(f"Error: Record Date {record_date} != Yesterday's Date {yesterday}")
        # print("Stopped. Please update database and try again.")
        pass
    else:
        pass
    
    # Calculate Position -- forecast should be positive or negative
    quantity, side, new_position = calculate_position('BTCUSDT', prev_position, BTC_price, sub_equity, forecast, decimals = 3)

    # Send order if needed
    if quantity != 0:
        code = 'New Position!'
        order = f"{side} {quantity} {symbol}"
        order_response = binanceOrder(client, side, quantity, symbol)
    else:
        new_position = prev_position
        code = 'Unchanged'
        order = 'No order sent.' 
    print(order)

    # Get updated USDT balance and BTC position.
    positions = client.futures_position_information()
    BTC_position = float(next(item for item in positions if item["symbol"] == 'BTCUSDT')['positionAmt'])

    print(f'Prev Position: {prev_position}')
    print(f'New Position: {BTC_position}')
    print('---------')

    # Create Info List
    info1 = [('Code', code),
            ('Prev Position', prev_position),
            ('New Position', new_position),
            ('Order', order)]
    # Calculations:
    info2 = [('Subsystem Equity', sub_sign + str(round(sub_equity, 2))),
            ('Forecast', forecast),
            ('BTC Price', sub_sign + str(round(BTC_price,2))),
            ('New Position', new_position),
            ('Trading Mode', trading_mode)]

    # Telegram
    message = '*' + symbol + '*\n\n'
    
    info1_message = info1.copy()
    info2_message = info2.copy()
    for item in info1_message:
        message += str(item[0]) + ': ' + str(item[1]) + '\n'
    message += '\n*Calculations*\n'
    for item in info2_message:
        message += str(item[0]) + ': ' + str(item[1]) + '\n'
    
    tg.outbound(message)

    # Return
    return dict(info1 + info2)

if __name__ == '__main__':
    main()