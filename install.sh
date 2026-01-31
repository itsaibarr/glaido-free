#!/bin/bash
# Glaido Installation Script for Fedora Linux

set -e

echo "========================================"
echo "🎤 Glaido Installer"
echo "========================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/glaido"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}⚠️  This script needs sudo for system-wide installation.${NC}"
    echo "Re-running with sudo..."
    exec sudo "$0" "$@"
fi

echo ""
echo "📦 Installing system dependencies..."
dnf install -y python3-devel python3-tkinter libnotify xclip 2>/dev/null || true

echo ""
echo "📦 Installing Python dependencies..."
pip3 install --upgrade sounddevice scipy groq numpy python-xlib pystray Pillow 2>/dev/null || \
pip install --upgrade sounddevice scipy groq numpy python-xlib pystray Pillow

echo ""
echo "📁 Creating installation directory..."
mkdir -p "$INSTALL_DIR"

echo "📋 Copying files..."
cp "$SCRIPT_DIR/glaido.py" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/glaido.py"

echo ""
echo "🖥️  Installing desktop entry..."
cp "$SCRIPT_DIR/glaido.desktop" /usr/share/applications/

echo ""
echo "⚙️  Installing systemd service..."
SYSTEMD_USER_DIR="/home/$SUDO_USER/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"
cp "$SCRIPT_DIR/glaido.service" "$SYSTEMD_USER_DIR/"
chown -R "$SUDO_USER:$SUDO_USER" "/home/$SUDO_USER/.config/systemd"

echo ""
echo "🚀 Enabling auto-start..."

# Get the actual user's runtime directory
USER_RUNTIME_DIR="/run/user/$(id -u $SUDO_USER)"

# Enable service as the actual user with proper environment
sudo -u "$SUDO_USER" XDG_RUNTIME_DIR="$USER_RUNTIME_DIR" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=$USER_RUNTIME_DIR/bus" \
    systemctl --user daemon-reload

sudo -u "$SUDO_USER" XDG_RUNTIME_DIR="$USER_RUNTIME_DIR" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=$USER_RUNTIME_DIR/bus" \
    systemctl --user enable glaido.service

echo ""
echo -e "${GREEN}========================================"
echo "✅ Installation Complete!"
echo "========================================"
echo ""
echo "To start Glaido now:"
echo "  systemctl --user start glaido"
echo ""
echo "Or search 'Glaido' in your app launcher."
echo ""
echo "Hotkey: Ctrl+Shift+Space"
echo "========================================${NC}"
