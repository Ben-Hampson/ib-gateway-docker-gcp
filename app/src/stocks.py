import json
import logging
import math
import os
import pprint
import random
import sys
import asyncio
import nest_asyncio
import asyncio
from database import connect
from datetime import date, timedelta
from decimal import Decimal

from fastapi import FastAPI
from ib_insync import IB, MarketOrder, Stock, util
from pydantic import BaseModel
from forex_python.converter import CurrencyCodes, CurrencyRates

import subsystems
import telegram_bot as tg
from position_size import calculate_position, round_decimals_down

cc = CurrencyCodes()
cr = CurrencyRates()

async def main():
    nest_asyncio.apply()
    if os.getenv('TRADING_MODE') == 'live':
        trading_mode = 'Live'
    else:
        trading_mode = 'Paper'

    ib = IB()
    with await ib.connectAsync(host=os.getenv('IB_GATEWAY_URLNAME', 'tws'), 
                               port=int(os.getenv('IB_GATEWAY_URLPORT', '4004')), 
                               clientId=int(os.getenv('EFP_CLIENT_ID', (5+random.randint(0, 4)))), 
                               timeout=15, 
                               readonly=False):
        ib.reqMarketDataType(4)
        print('IB Connected')
        
        for sub in subsystems.db:
            if sub['type'] == 'stock':
                symbol = sub['symbol']
                
                # Subsystem Info
                try:
                    sub = next(item for item in subsystems.db if item['symbol'] == symbol)
                    print('Subsystem info found')
                except:
                    print(f'Error: {symbol} can not be found in subsystems.py')
                    tg.outbound(f'⚠️ *Warning: {symbol} was not found in subsystems info!*')
                    # break

                # Currency Symbol
                sub_currency = sub['currency']
                if sub_currency == 'USD' or sub_currency == 'USDT':
                    sub_sign = '$'
                else:
                    sub_sign = cc.get_symbol(sub_currency)

                # FX Rate - Assumes account balance is in GBP
                if sub_currency != 'GBP':
                    fx = cr.get_rate('GBP', sub_currency)
                    print(f'GBP{sub_currency} FX Rate: {fx}')
                else:
                    fx = 1
                    print('Currency is GBP - FX Rate = 1')
                
                # IB Equity - in GBP
                accountSummary = util.tree(await ib.accountSummaryAsync(account = os.getenv('TWSACCOUNTID')))
                IB_equity = float(next(item for item in accountSummary if item["tag"] == 'NetLiquidation')['value'])
                IB_equity_cc = cc.get_symbol(next(item for item in accountSummary if item["tag"] == 'NetLiquidation')['currency'])
                print(f'IB Equity: {IB_equity_cc}{IB_equity}')

                # Subsystem Equity - converted to currency we're trading the instrument in
                sub_equity = round_decimals_down((IB_equity * sub["broker-weight"] * fx), 2)
                print(f'Subsystem Equity: {sub_sign}{sub_equity}')
                
                # Get Contract + Contract Details from IB
                try:
                    contract = Stock((symbol), 'SMART', sub_currency)
                except:
                    print(f'No contract exists: {symbol}')
                    tg.outbound(f'⚠️ *Warning: No contract exists: {symbol}*.')
                contract_details = util.tree(await ib.reqContractDetailsAsync(contract))
                contract_id = contract_details[0]['ContractDetails']['contract']['Contract']['conId']
                contract_symbol = contract_details[0]['ContractDetails']['contract']['Contract']['symbol']  # What is this necessary for?
                contract_longname = contract_details[0]['ContractDetails']['longName']
                print(f'{contract_symbol} - {contract_longname} - {contract_id}')

                # Get Current Position
                positions = util.tree(await ib.reqPositionsAsync())
                try:
                    contract_position_details = next(item for item in positions if item['contract']['Stock']['conId'] == contract_id)
                    position_existed = True
                    prev_position = float(contract_position_details['position'])
                    print(f'{contract_symbol} Position: {prev_position}')
                except:
                    position_existed = False
                    prev_position = 0
                    tg.outbound(f'⚠️ *Warning: No previous position exists for {contract_symbol} - {contract_longname}*.')
                print(f'Position Existed: {position_existed}')
                
                market_data = ib.reqMktData(contract = contract, snapshot = True)
                ib.sleep(5)
                print(market_data)
                stock_price = market_data.close # This the is the close price. Ideally we want the live price.
                print(f"Stock Price (Yesterday's Close): {stock_price}")

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
                    pass
                else:
                    pass

                # Calculate Position -- forecast should be positive or negative
                quantity, side, new_position = calculate_position(symbol, prev_position, stock_price, sub_equity, forecast, 0)

                # Send order if needed
                if quantity != 0:
                    code = 'New Position!'
                    order_info = f"{side} {quantity} {contract_symbol}"
                    print('Order:', order_info)
                    
                    order = MarketOrder(side, quantity)
                    trade = ib.placeOrder(contract, order)
                    order_response = util.tree(trade)
                    print(f"IB Order Response: {order_response}")
                    trade.log
                else:
                    new_position = prev_position
                    code = 'Unchanged'
                    order_info = 'No order sent.'
                    print(order_info)

                print('----------------------')

                # ===============================

                # Create Info Lists
                info1 = [('Code', code),
                        ('Prev Position', prev_position),
                        ('New Position', new_position),
                        ('Order', order_info)]
                # Calculations:
                info2 = [('Subsystem Equity', sub_sign + str(sub_equity)),
                        ('Forecast', forecast),
                        ('Price', sub_sign + str(stock_price)),
                        ('New Position', new_position),
                        ('Trading Mode', trading_mode)]

                # Telegram
                message = '*' + contract_symbol + ' - ' + contract_longname + '*\n\n'
                
                info1_message = info1.copy()
                info2_message = info2.copy()
                for item in info1_message:
                    message += str(item[0]) + ': ' + str(item[1]) + '\n'
                message += '\n*Calculations*\n'
                for item in info2_message:
                    message += str(item[0]) + ': ' + str(item[1]) + '\n'
                
                tg.outbound(message)

                print(f'{symbol}: Complete')
    print('Finished.')

if __name__ == "__main__":
    asyncio.run(main())