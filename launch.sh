#!/bin/bash

ROOT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PID_FILE="$ROOT_PATH/bot.pid"

# Kill existing process if PID file exists
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "Killing existing process: $OLD_PID"
        kill $OLD_PID
        sleep 2
        kill -9 $OLD_PID 2>/dev/null
    fi
fi

# Activate venv and start the bot
. "$ROOT_PATH/venv/bin/activate"
python "$ROOT_PATH/disco-robo.py" > "$ROOT_PATH/log.file" 2>&1 &

# Save new PID
echo $! > "$PID_FILE"
echo "Bot started with PID: $!"
