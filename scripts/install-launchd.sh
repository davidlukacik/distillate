#!/usr/bin/env bash
#
# Install a macOS Launch Agent for papers-workflow.
# Runs the sync every 15 minutes and logs to ~/Library/Logs/.
#
set -euo pipefail

LABEL="com.papers-workflow.sync"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG="$HOME/Library/Logs/papers-workflow.log"

# Resolve repo root (parent of scripts/)
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EXECUTABLE="${REPO_DIR}/.venv/bin/papers-workflow"

# Verify prerequisites
if [[ ! -x "$EXECUTABLE" ]]; then
    echo "Error: $EXECUTABLE not found."
    echo "Run 'uv pip install -e .' from the repo root first."
    exit 1
fi

RMAPI="$(command -v rmapi 2>/dev/null || true)"
if [[ -z "$RMAPI" ]]; then
    echo "Error: rmapi not found in PATH."
    echo "Install it: https://github.com/ddvk/rmapi/releases"
    exit 1
fi

# Build PATH: include the directory containing rmapi
RMAPI_DIR="$(dirname "$RMAPI")"
LAUNCH_PATH="/usr/local/bin:/usr/bin:/bin"
if [[ ":$LAUNCH_PATH:" != *":$RMAPI_DIR:"* ]]; then
    LAUNCH_PATH="${RMAPI_DIR}:${LAUNCH_PATH}"
fi

# Unload existing agent if present
if launchctl list "$LABEL" &>/dev/null; then
    echo "Unloading existing agent..."
    launchctl unload "$PLIST" 2>/dev/null || true
fi

# Ensure LaunchAgents directory exists
mkdir -p "$HOME/Library/LaunchAgents"

# Write the plist
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${EXECUTABLE}</string>
    </array>

    <key>StartInterval</key>
    <integer>900</integer>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>${LAUNCH_PATH}</string>
    </dict>

    <key>StandardOutPath</key>
    <string>${LOG}</string>
    <key>StandardErrorPath</key>
    <string>${LOG}</string>

    <key>Nice</key>
    <integer>10</integer>
</dict>
</plist>
EOF

# Load the agent
launchctl load "$PLIST"

echo "Installed and loaded: $LABEL"
echo ""
echo "  Plist:      $PLIST"
echo "  Executable: $EXECUTABLE"
echo "  Schedule:   every 15 minutes"
echo "  Log:        $LOG"
echo ""
echo "Useful commands:"
echo "  launchctl start $LABEL          # run now"
echo "  tail -f $LOG                    # watch logs"
echo "  launchctl unload $PLIST         # stop"
