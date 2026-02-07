#!/usr/bin/env bash
#
# Uninstall the macOS Launch Agent for papers-workflow.
#
set -euo pipefail

LABEL="com.papers-workflow.sync"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

if [[ ! -f "$PLIST" ]]; then
    echo "Nothing to uninstall: $PLIST does not exist."
    exit 0
fi

launchctl unload "$PLIST" 2>/dev/null || true
rm "$PLIST"

echo "Uninstalled: $LABEL"
echo "Log file kept at: $HOME/Library/Logs/papers-workflow.log"
