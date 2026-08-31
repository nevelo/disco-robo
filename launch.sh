#!/bin/bash

set -u

BOT_SERVICE="disco-robo"

# Matches "disco-robo.py" whether invoked with an absolute path, a relative
# path, or as a bare filename, so rogue copies are caught regardless of how
# they were launched.
BOT_MATCH_PATTERN='(^|[/ ])disco-robo\.py([ ]|$)'

# `systemctl restart` only touches the process systemd itself tracks as the
# unit's MainPID. It has no awareness of a copy started manually outside the
# service (e.g. `python disco-robo.py` from a shell) -- that copy would keep
# running and double-handle Discord events. Sweep for exactly that case, then
# let systemd handle stopping/starting its own managed copy atomically.
MANAGED_PID=$(systemctl show -p MainPID --value "$BOT_SERVICE" 2>/dev/null || echo 0)

for pid in $(pgrep -f -- "$BOT_MATCH_PATTERN"); do
    if [ "$pid" != "$MANAGED_PID" ]; then
        echo "Killing rogue disco-robo.py process not managed by systemd (PID $pid)"
        kill -TERM "$pid" 2>/dev/null || true
        sleep 2
        kill -KILL "$pid" 2>/dev/null || true
    fi
done

systemctl restart "$BOT_SERVICE"
