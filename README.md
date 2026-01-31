# Glaido - Voice Transcription for Linux

A lightweight voice transcription app for Fedora Linux using Groq Whisper API.

## Features

- **Global Hotkey**: `Ctrl+Shift+Space` works from any application
- **System Tray**: Visual indicator (green = ready, red = recording)
- **Desktop Notifications**: Shows transcription result
- **Clipboard Integration**: Auto-copies transcription for easy paste
- **Auto-start**: Runs automatically on login

## Installation

```bash
# Clone the repo
cd ~/projects/glaido-free

# Run installer (needs sudo)
./install.sh
```

## Usage

1. Press `Ctrl+Shift+Space` to start recording
2. Speak your message
3. Press `Ctrl+Shift+Space` again to stop
4. Transcription is auto-copied to clipboard
5. Paste anywhere with `Ctrl+V`

## Manual Start

```bash
# Start the service
systemctl --user start glaido

# Check status
systemctl --user status glaido

# View logs
journalctl --user -u glaido -f
```

## Dependencies

- Python 3.10+
- sounddevice, scipy, groq, numpy
- python-xlib, pystray, Pillow
- libnotify, xclip

## Troubleshooting

**Hotkey not working?**
- Make sure you're running X11 (not Wayland)
- Check: `echo $XDG_SESSION_TYPE`

**No sound recording?**
- Check microphone permissions
- Run: `pavucontrol` to verify input device

## License

MIT
