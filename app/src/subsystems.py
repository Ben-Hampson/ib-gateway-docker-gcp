db = [
    {
        'symbol':'BTCUSDT',
        'type': 'crypto',
        'broker':'Binance',
        'data_source': 'Binance',
        'data_symbol': '',
        'currency':'USDT',
        'broker-weight':1,
        'overall-weight':0.33,
        'block':'',
        'idm':'',
    },
    {
        'symbol':'AAPL',
        'type': 'stock',
        'broker':'IB',
        'data_source': 'Alpha Vantage',
        'data_symbol': 'AAPL',
        'currency':'USD',
        'broker-weight':0.5,
        'overall-weight':0.33,
        'block':1,
        'idm':'',
    },
    {
        'symbol':'BARC',
        'type': 'stock',
        'broker':'IB',
        'data_source': 'Yahoo',
        'data_symbol': 'BARC.L',
        'currency':'GBP',
        'broker-weight':0.5,
        'overall-weight':0.33,
        'block':1,
        'idm':'',
    }
]

if __name__ == '__main__':
    print('subsystems.py running')