# tradebot
*A framework to automate a trading strategy on both Interactive Brokers and Binance.*

This project builds upon [@mvberg](https://github.com/mvberg/ib-gateway-docker)'s initial containerisation of IBGW + IBC, and [@dvasekis](https://github.com/dvasdekis/ib-gateway-docker-gcp)'s optimisation and extension of it. It features:

* Connection to Binance Futures as well as Interactive Brokers
* [IBC 3.8.4-beta.2](https://github.com/IbcAlpha/IBC) - adds the ability to retry sending 2FA notifications to your phone if you missed them
* A portfolio of instruments
* The ability to trade any stock/ETF on IB in a variety of currencies
* Pulls historic stock + crypto closes from CryptoCompare, Alpha Vantage, and Yahoo Finance
* An SQLite database to hold closes, EMA data (or whatever indicator you want), and a forecast for each instrument
* Easily customisable strategy and position-sizing
* Runs your strategy automatically daily
* A Telegram bot that reports trades upon completion

This works nicely either locally or on a server. I haven't tested it on GCP/AWS.

* IB Gateway: v978.2c
* IBC: v3.8.4-beta2

**Note: This is a project in development! If you must, only use this in paper trading mode! Furthermore, the given strategy (EMA 5/20 crossover) is just an example and in no way recommended as a trading strategy! Check the limitations below.**

### Getting Started

In order to use certain aspects of the bot, you'll need to add your credentials:

1. Add your Interactive Brokers User ID, password, and Account ID to `.env.template` and rename it to `.env`.
2. (Optional) Add your API keys and credentials for the services you want to `/app/src/.env.template` and rename it to `.env`:
    * [Binance API Key + Secret Key](https://www.binance.com/en/support/faq/360002502072-How-to-create-API) (make sure you tick 'Enable Futures')
    * [CryptoCompare API Key](https://min-api.cryptocompare.com/) (for getting BTCUSDT historical closes)
    * [Alpha Vantage API Key](https://rapidapi.com/alphavantage/api/alpha-vantage) (via RapidAPI)

Yahoo Finance is often a good source of historical data and doesn't require an API key so you could just that. However, no one provider of historical stock data is perfect. Therefore if Yahoo Finance doesn't have a complete history for your stock, try Alpha Vantage. Once you know which provider is best, add it to that instrument's info in subsystems.py (see below).

```
git clone
docker-compose build
docker-compose up
```

### How It Works
#### Database
Once spun up, `database.py` creates a database if it doesn't exist. It creates a table for each instrument in `subsystems.py`. Then it will check the status of those tables to see if they are up to date with the most recent daily closes or not. If not, it will pull them from the `data_source` attribute of each instrument and insert them into the database.

#### Strategy
`database.py` then looks to `strategy.py` in order to calculate something from those closes. In this example, the strategy is calculating the EMA 5 and EMA 20. It then uses those EMAs to create a forecast. This is important for calculating our position later. This forecast is created by subtracting the EMA 20 from the EMA 20. If the result is positive, we want to go long. If the result is negative, we want to go short. Simple. For each instrument in `subsystems.py`, `database.py` will use `strategy.py` to calculate our EMAs and forecast, and update the table with that data.

#### Calculating Orders
`stocks.py` and `crypto.py` will then go through the relevant instruments in `subsystems.py`, and for each it will consider your IB or Binance equity, the FX rate (if necessary), the current price, your current position, and the forecast the strategy created. It then uses `position_size.py` to work out if we need to change our position, and if so, how much we need to buy/sell in order to get from our current position to the forecast's desired position of long or short. It then hands back to `stocks.py` and `crypto.py`, which will make the necessary orders. Finally, if set up, it can send you a message via a Telegram bot that runs in the `app` container. 

#### Daily Automation
`app/root` contains the cron jobs that run daily. `database.py` will get the recent closes and update the forecasts at 00:15. `crypto.py` and `stocks.py` will calculate and make your orders at 00:20 and 00:25 respectively.

### Customising Your Portfolio + Preferences

* Your portfolio can be customised in `app/src/subsystems.py`.
* Your strategy can be customised in `app/src/strategy.py`.
* Your position sizing method can be customised in `app/src/position_size.py`.
* If you want to use a Telegram Bot, you'll need to:
    - Set up your bot [here](https://core.telegram.org/bots#6-botfather).
    - Add your bot's token to `app/.env`.
    - Get your personal Telegram's chat ID from [@getmyid_bot](https://t.me/getmyid_bot?do=open_link) and add it to `app/.env`.
* The timing of the cron jobs can be customised in `app/root`.

### Limitations
There are a few limitations that I want to work on in the future:
- `crypto.py` can only trade BTCUSDT futures
- Leverage is entirely disabled (probably a wise idea for most of us, anyway!).
- `stocks.py` assumes your IB account base currency is GBP
- `database.py` and `stocks.py` currently calculate and order for all the stocks in portfolio at once. That's fine if you have stocks only from one exchange, but when you have stocks on a variety of exchanges that open and close at different times, it's not ideal. It would be nice to set custom cron times for each instrument.

The bot only works with daily close data and runs daily. I don't intend to shorten that timeframe.

#### Logging in with VNC:

1. SSH into server and run `mkdir ~/.vnc && echo "mylongpassword" > ~/.vnc/passwd && x11vnc -passwd mylongpassword -display ":99" -forever -rfbport 5900` as root
2. Log in with a remote VNC client using `mylongpassword` on port 5901

**Note: All IPs on your network are able to connect to your box and place trades - so please do not open your box to the internet.**

##### Read-Only API warning:
IBC has decided not to support switching off the Read-Only checkbox (on by default) on the API Settings page.

To work around it for some operations, you'll need to write a file called ibg.xml as a new file to `/root/Jts/*encrypted user id*/ibg.xml`. The ibg.xml file can be found in this folder after a successful run and close, and contains the application's settings from the previous run.

Please contact me if you have any thoughts, ideas, or questions!
