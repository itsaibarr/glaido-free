# Glaido

Status: paused since March 2026.

**Advanced Voice Transcription & AI Prompt Assistant for Linux**

Glaido is a technical background service designed for professional workflows. It transforms spoken intent into structured text or optimized AI prompts using the Groq Whisper and Llama 3 APIs.

## ⚡ Core Features

- **Multi-Mode STT Pipeline**:
  - **Transcribe Mode**: Precise, raw speech-to-text.
  - **AI Prompt Mode**: High-density intent compression using `llama-3.3-70b-versatile`.
- **Intelligent I/O Layer**:
  - **Direct Typing**: Simulates keyboard input into the active window (supports `wtype`, `ydotool`, `xdotool`).
  - **Clipboard Sync**: Fallback clipboard integration for all transmittals.
- **System Integration**:
  - **Global Hotkeys**: Control recording and modes from any application.
  - **Audio Ducking**: Automatically mutes system audio during recording for clean capture.
  - **Visual Feedback**: System tray indicators and rich desktop notifications with transcription previews.
  - **Recording Control**: `Escape` to cancel any ongoing recording immediately.

## 🎹 Keyboard Shortcuts

| Shortcut               | Action                               |
| :--------------------- | :----------------------------------- |
| `Ctrl + Shift + Space` | Toggle Recording (Start/Stop)        |
| `Ctrl + Shift + M`     | Switch Mode (Transcribe ↔ AI Prompt) |
| `Escape`               | Cancel Recording                     |

## 🛠 Installation

### 1. Environment Setup

Register for a Groq API Key at [console.groq.com](https://console.groq.com/keys).

```bash
# Clone the repository
cd ~/projects/glaido-free

# Setup credentials
echo "GROQ_API_KEY=your_actual_key" > .env
```

### 2. Deployment

The automated installer handles dependencies, systemd service registration, and X11 hotkey configuration.

```bash
./install.sh
```

## 📦 Dependencies

- **Core**: Python 3.10+, `sounddevice`, `numpy`, `scipy`, `groq`
- **Interface**: `python-xlib`, `pystray`, `Pillow`, `libnotify`
- **Input Simulation**: `wtype` (Wayland), `ydotool` (Generic), or `xdotool` (X11)
- **Audio Control**: `pactl` (PulseAudio/PipeWire)

## 🔍 Troubleshooting

- **Wayland Support**: For hotkeys on Wayland, ensure you have `wtype` or `ydotool` installed and configured.
- **Audio Input**: Use `pavucontrol` to verify your primary microphone is active if recording seems silent.
- **Logs**: Monitor the background service via `journalctl --user -u glaido -f`.

---

_MIT License • Built for high-efficiency Linux environments._
