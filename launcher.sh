#!/bin/bash

cd "$(dirname "$0")" || exit
python3 -u main.py >> ../FSBot-data/logging/discord_bot.out 2>&1