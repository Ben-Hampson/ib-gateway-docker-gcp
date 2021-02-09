import sqlite3
import subsystems
import requests
import numpy as np
import pandas as pd
import tulipy as ti
import yahoo_fin.stock_info as si
import pandas_datareader as pdr
import strategy
from datetime import datetime, timedelta, date
from pathlib import Path
from decouple import config

def connect():
    path = Path(__file__).parent
    APP_DB = path / 'data.db'
    
    connection = sqlite3.connect(APP_DB)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    return connection, cursor

def create_database():
    print(f"--- 'CREATING' TABLES ---")

    connection, cursor = connect()

    for sub in subsystems.db:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {sub['symbol']}(
                date NOT NULL UNIQUE PRIMARY KEY,
                close NOT NULL,
                ema_5,
                ema_20,
                forecast
            )""")

    connection.commit()

    print("--- Tables 'Created' ---")

def check_table_status(symbol:str):
    # Note: what happens if it's freshly created and empty?
    print(f'--- {symbol} Status ---')
    connection, cursor = connect()

    # Get yesterday's date so we begin with yesterday's close (00:00)
    today = datetime.now()
    oneDay = timedelta(days=1)
    yesterday = today - oneDay
    yesterday_date = yesterday.strftime('%Y-%m-%d')
    toTimestamp = int(datetime.timestamp(yesterday))
    print(f'toTimestamp: {yesterday_date}')

    # Get latest records
    cursor.execute(f"""
        SELECT date, close
        FROM {symbol}
        ORDER BY date ASC
        """)
    
    rows = cursor.fetchall()

    if len(rows) == 0:
        print(f'{symbol} table is EMPTY.')
        up_to_date = False
        empty = True
        latestDate = ''
    else:
        # No. of Records
        print(f'{symbol} records: {len(rows)}')

        # Get the most recent record's date
        latestDate = rows[-1]['date']
        print(f'Latest Date in {symbol} table: {latestDate}')

        # Determine if table is up to date, or not, or empty
        if latestDate == yesterday_date:
            up_to_date = True
            empty = False
            print(f'{symbol} table up to date. No update needed.')
        else:
            up_to_date = False
            empty = False
            print(f'{symbol} table NOT up to date.') 

    print(f'--- Finished checking {symbol} table ---')

    return empty, up_to_date, latestDate

def get_Binance_data(empty: bool, latestDate: str):
    # Currently assumes symbol is BTCUSDT
    print(f'--- BTCUSDT: Populating Table ---')
    connection, cursor = connect()

    # Get yesterday's date so we begin with yesterday's close (00:00)
    today = datetime.now()
    oneDay = timedelta(days=1)
    yesterday = today - oneDay
    yesterday_date = yesterday.strftime('%Y-%m-%d')
    toTimestamp = int(datetime.timestamp(yesterday))
    print(f'toTimestamp: {yesterday_date}')

    # Do we have items in the table?
    cursor.execute("""SELECT *
                      FROM BTCUSDT
                      ORDER BY date ASC""")
    
    rows = cursor.fetchall()

    close_array_rev = []
    date_array_rev = []

    if empty:
        end = False
        limit = 1000
        print('BTCUSDT table empty. Populating all available historic data.')

        while end == False:
            data = requests.get('https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD' + 
                                '&limit=' + str(limit) + 
                                '&toTs=' + str(toTimestamp) + 
                                '&api_key=' + config('CC_API_KEY')).json()

            for bar in reversed(data['Data']['Data']):
                timestamp = datetime.fromtimestamp(bar['time'])
                date = timestamp.strftime('%Y-%m-%d')
                close = bar['close']
                if close == 0:
                    end = True
                    print('Close = 0. Break.')
                    break

                close_array_rev.append(close)
                date_array_rev.append(date)
            
            # Get 'TimeFrom', take away 1 day, and then use it as 'toTimestamp' next time
            TimeFrom = data['Data']['TimeFrom']
            minusOneDay = datetime.fromtimestamp(TimeFrom) - oneDay
            toTimestamp = datetime.timestamp(minusOneDay)

    else:  # If not empty and not up to date
        print(f'Latest Date in BTCUSDT table: {latestDate}')

        # Get latestDate in Unix Time, to use as fromTime in API request
        last = latestDate.split('-')
        latestDateDT = datetime(int(last[0]), int(last[1]), int(last[2]))

        # Set API limit
        dateDiff = yesterday - latestDateDT
        limit = dateDiff.days  
        print(f'# of days to get close data for: {limit}')

        # Request data from API
        data = requests.get('https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD' + 
                                '&limit=' + str(limit) + 
                                '&toTs=' + str(toTimestamp) + 
                                '&api_key=' + config('CC_API_KEY')).json()

        for bar in reversed(data['Data']['Data'][1:]): # The API returns one more than you asked for, so ignore the first
            timestamp = datetime.fromtimestamp(bar['time'])
            date = timestamp.strftime('%Y-%m-%d')
            close = bar['close']
            print(f'{date} - {close}')

            close_array_rev.append(close) # Returns: First = latest, last = oldest.
            date_array_rev.append(date)

    # Reverse arrays so that first = oldest, last = latest
    close_array = np.flip(np.array(close_array_rev))
    date_array = np.flip(np.array(date_array_rev))
    
    dates_closes = list(zip(date_array, close_array))

    return dates_closes

def get_AlphaVantage_data(symbol: str, data_symbol: str, empty: bool, latestDate: str):
    data = pdr.av.time_series.AVTimeSeriesReader(symbols=data_symbol, 
                                          function='TIME_SERIES_DAILY_ADJUSTED', 
                                          api_key=config('AV_API_KEY')).read()

    data['date'] = data.index
    data['date'] = data.date.apply(lambda x: datetime.strptime(x, "%Y-%m-%d").date())

    # Get yesterday's date so we begin with yesterday's close (00:00)
    today = datetime.now()
    oneDay = timedelta(days=1)
    yesterday = today - oneDay

    if empty:
        data = data[(data.date <= yesterday.date())]
    else:
        latestDate = datetime.strptime(latestDate, "%Y-%m-%d").date()
        data = data[(data.date > latestDate) & (data.date <= yesterday.date())]

    dates = [i.strftime('%Y-%m-%d') for i in data.date]
    closes = np.around(data['close'].to_list(), 2)
    dates_closes = list(zip(dates, closes))
    
    return dates_closes

def get_YFinance_data(symbol: str, data_symbol: str, empty: bool, latestDate: str):
    data = si.get_data(data_symbol)

    # Get yesterday's date so we begin with yesterday's close (00:00)
    today = datetime.now()
    oneDay = timedelta(days=1)
    yesterday = today - oneDay

    if empty:
        data = data[(data.index.date <= yesterday.date())]
    else:
        latestDate = datetime.strptime(latestDate, "%Y-%m-%d").date()
        data = data[(data.index.date > latestDate) & (data.index.date <= yesterday.date())]


    dates = [i.strftime('%Y-%m-%d') for i in data.index.date]
    closes = np.around(data['close'].to_list(), 2)
    dates_closes = list(zip(dates, closes))

    return dates_closes

def insert_closes_into_table(symbol: str, dates_closes: list):
    connection, cursor = connect()

    records = 0
    errors = 0

    for i in dates_closes:
        try:
            cursor.execute(f"""
                INSERT INTO {symbol} (date, close)
                VALUES (?, ?)
                """,
                (i[0], i[1]))
            records += 1
        except Exception as e:
            print(f'Exception: {e}')
            errors += 1
    
    connection.commit()

    print(f'--- {symbol}: table populated ---')
    print(f'Records Added: {records}')
    print(f'Errors: {errors}')

def drop_tables():
    print(f'--- DROPPING TABLES ---')
    connection, cursor = connect()

    for sub in subsystems.db:
        cursor.execute(f"""
            DROP TABLE {sub['symbol']}
            """)

    print('--- TABLES DROPPED ---')

if __name__ == '__main__':
    create_database()  # If there are no tables, it'll create them; otherwise, it'll do nothing.
    for sub in subsystems.db:
        symbol = sub['symbol']
        data_symbol = sub['data_symbol']

        empty, up_to_date, latestDate = check_table_status(symbol)

        if up_to_date == False:
            print(f'{symbol} table NOT up to date. Updating.')
            
            if sub['data_source'] == 'Binance':
                dates_closes = get_Binance_data(empty, latestDate)
            elif sub['data_source'] == 'Yahoo':
                dates_closes = get_YFinance_data(symbol, data_symbol, empty, latestDate)
            elif sub['data_source'] == 'Alpha Vantage':
                dates_closes = get_AlphaVantage_data(symbol, data_symbol, empty, latestDate)

            insert_closes_into_table(symbol, dates_closes)
            strategy.calculate_EMAs(symbol)

    print('Finished database.py')
        
