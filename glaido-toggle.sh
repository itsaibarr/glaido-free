#!/bin/bash
# Glaido Toggle - Simple click-to-record script

# Path to toggle signal file
TOGGLE_FILE="/tmp/glaido_toggle_signal"

# Create/update the toggle file with current timestamp
echo "$(date +%s%N)" > "$TOGGLE_FILE"
