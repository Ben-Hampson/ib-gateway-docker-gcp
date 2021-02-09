#!/bin/sh
echo "Welcome to tradebot 2.2"
service cron start
service cron status
echo "Updating database"
python3 /tmp/src/database.py
echo "Starting server"
python3 /tmp/src/app.py