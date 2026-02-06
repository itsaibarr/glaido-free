# Glaido - Voice Transcription for Linux

A lightweight voice transcription app for Fedora Linux using Groq Whisper API.

## Features

- **Global Hotkey**: `Ctrl+Shift+Space` works from any application
- **System Tray**: Visual indicator (green = ready, red = recording)
- **Desktop Notifications**: Shows transcription result
- **Clipboard Integration**: Auto-copies transcription for easy paste
- **Auto-start**: Runs automatically on login

## Installation

### 1. Setup Environment Variables

Create a `.env` file with your Groq API key:

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your API key
# Get your API key from: https://console.groq.com/keys
nano .env
```

Your `.env` file should contain:
```
GROQ_API_KEY=your_actual_api_key_here
```

**⚠️ IMPORTANT**: Never commit the `.env` file to version control. It's already in `.gitignore`.

### 2. Run Installation

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
- python-dotenv (for environment variables)
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
