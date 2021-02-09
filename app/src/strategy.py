import sqlite3
from pathlib import Path
import tulipy as ti
import numpy as np

def connect():
    path = Path(__file__).parent
    APP_DB = path / 'data.db'
    
    connection = sqlite3.connect(APP_DB)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    return connection, cursor

def ema_array(close_array: list, ema_length: int):
    ema = ti.ema(close_array, ema_length)
    ema_array = np.around(ema, 2)
    
    return ema_array

def make_forecast(fast_ema_array: list, slow_ema_array: list):
    """Take fast and slow EMAs, subtract the slow from the fast, this returns a long, short, or flat position.
    Fast EMA above slow EMA means go long. Fast EMA below slow EMA means go short. EMAs equivalent means take no position.
    The size of the forecast is irrelevant to us. We'll just use the positive/negative/0 part."""

    raw_forecast = np.subtract(fast_ema_array, slow_ema_array)
    raw_forecast = np.around(raw_forecast, 2)

    forecast = list(raw_forecast)
    
    return forecast

def calculate_EMAs(symbol: str):
    print(f'--- {symbol}: Updating EMAs ---')
    connection, cursor = connect()

    cursor.execute(f"""
        SELECT date, close
        FROM {symbol}
        ORDER BY date ASC
        """)

    rows = cursor.fetchall()

    close_data = [row['close'] for row in rows]
    date_data = [row['date'] for row in rows]

    close_array = np.array(close_data)  # First = Oldest. Last = Latest

    ema5_array = ema_array(close_array, 5)
    ema20_array = ema_array(close_array, 20)

    forecast = make_forecast(ema5_array, ema20_array)

    input = list(zip(ema5_array, 
                    ema20_array,
                    forecast,
                    date_data))

    # Update table with the EMAs and forecast for each date
    records = 0
    errors = 0

    for i in input:
        try:
            cursor.execute(f"""
                UPDATE {symbol}
                SET ema_5 = ?,
                    ema_20 = ?,
                    forecast = ?
                WHERE date = ?
                """,
                (i[0], i[1], i[2], i[3]))
            records += 1
        except Exception as e:
            print(f'Exception: {e}')
            errors += 1

    connection.commit()

    print(f'--- {symbol}: EMAs updated ---')
    print(f'Records Updated: {records}')
    print(f'Errors: {errors}')