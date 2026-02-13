#!/usr/bin/env python3
"""
Glaido - Voice Transcription & AI Prompt Assistant (Background Service)

Pipeline: Hotkey -> Audio Capture -> STT -> Processing Layer -> Output Layer

Global hotkeys:
  Ctrl+Shift+Space  - Toggle recording
  Ctrl+Shift+M      - Switch mode (Transcribe / Prompt)
  Escape             - Cancel recording
"""

import os
import sys
import threading
import subprocess
import tempfile
import time
import shutil
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io import wavfile
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env file (in the same directory as this script)
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Try to import X11 for hotkeys
try:
    from Xlib import X, XK
    from Xlib.display import Display
    from Xlib.ext import record
    from Xlib.protocol import rq
    HAS_XLIB = True
except ImportError:
    HAS_XLIB = False

# ============================================================================
# Configuration
# ============================================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("Error: GROQ_API_KEY not found in environment variables.")
    print("Please create a .env file with your API key:")
    print("GROQ_API_KEY=your_api_key_here")
    sys.exit(1)

SAMPLE_RATE = 16000
CHANNELS = 1
TEMP_DIR = Path(tempfile.gettempdir())
AUDIO_FILE = TEMP_DIR / "glaido_recording.wav"
TOGGLE_FILE = Path("/tmp/glaido_toggle_signal")

# LLM model for prompt mode
LLM_MODEL = "llama-3.3-70b-versatile"

# System prompt for prompt mode
PROMPT_SYSTEM_INSTRUCTION = (
    "You are a speech-to-prompt converter. "
    "Convert the user's spoken text into a clean, structured AI prompt. "
    "Rules:\n"
    "- Remove all filler words (um, uh, like, you know, basically, etc.)\n"
    "- Compress the intent into a concise instruction\n"
    "- Return ONLY the optimized prompt, nothing else\n"
    "- No explanations, no preamble, no quotes\n"
    "- Keep it short and actionable"
)

# ============================================================================
# Audio Recording
# ============================================================================

class AudioRecorder:
    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.lock = threading.Lock()

    def _audio_callback(self, indata, frames, time, status):
        if self.recording:
            self.audio_data.append(indata.copy())

    def start(self):
        with self.lock:
            if self.recording:
                return False
            self.recording = True
            self.audio_data = []

        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype='int16',
            callback=self._audio_callback
        )
        self.stream.start()
        return True

    def stop(self):
        with self.lock:
            if not self.recording:
                return None
            self.recording = False

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_data:
            return None

        audio_array = np.concatenate(self.audio_data, axis=0)
        wavfile.write(str(AUDIO_FILE), SAMPLE_RATE, audio_array)
        return len(audio_array) / SAMPLE_RATE

    @property
    def is_recording(self):
        return self.recording

    def cancel(self):
        """Cancel recording without saving."""
        with self.lock:
            if not self.recording:
                return False
            self.recording = False

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        self.audio_data = []
        return True

# ============================================================================
# Audio Ducking (Mute Other Apps)
# ============================================================================

class AudioDucker:
    """Mute other applications during recording using PulseAudio/PipeWire."""

    def __init__(self):
        self.available = self._check_availability()
        self.muted_sinks = []

    def _check_availability(self):
        try:
            result = subprocess.run(
                ["pactl", "--version"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False

    def _get_sink_inputs(self):
        if not self.available:
            return []
        try:
            result = subprocess.run(
                ["pactl", "list", "sink-inputs", "short"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                sink_inputs = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split()
                        if parts:
                            sink_inputs.append(parts[0])
                return sink_inputs
        except Exception:
            pass
        return []

    def mute_others(self):
        if not self.available:
            return
        self.muted_sinks = self._get_sink_inputs()
        for sink_id in self.muted_sinks:
            try:
                subprocess.run(
                    ["pactl", "set-sink-input-mute", sink_id, "1"],
                    capture_output=True,
                    timeout=1
                )
            except Exception:
                pass

    def restore(self):
        if not self.available:
            return
        for sink_id in self.muted_sinks:
            try:
                subprocess.run(
                    ["pactl", "set-sink-input-mute", sink_id, "0"],
                    capture_output=True,
                    timeout=1
                )
            except Exception:
                pass
        self.muted_sinks = []

# ============================================================================
# Speech-to-Text (STT Layer)
# ============================================================================

def transcribe_audio():
    """Send audio to Groq Whisper API and return transcribed text."""
    if not AUDIO_FILE.exists():
        return None
    try:
        client = Groq(api_key=GROQ_API_KEY)
        with open(AUDIO_FILE, "rb") as f:
            result = client.audio.transcriptions.create(
                file=(AUDIO_FILE.name, f.read()),
                model="whisper-large-v3",
                response_format="text"
            )
        return result.strip() if result else None
    except Exception as e:
        print(f"STT Error: {e}")
        return None

# ============================================================================
# Processing Layer (Mode Switch)
# ============================================================================

class ProcessingLayer:
    """Processes transcribed text based on current mode."""

    MODES = ("transcribe", "prompt")

    def __init__(self):
        self._mode = "transcribe"

    @property
    def mode(self):
        return self._mode

    def toggle_mode(self):
        """Cycle to the next mode."""
        idx = self.MODES.index(self._mode)
        self._mode = self.MODES[(idx + 1) % len(self.MODES)]
        return self._mode

    def process(self, text):
        """Process text through the current mode pipeline."""
        if self._mode == "transcribe":
            return text
        elif self._mode == "prompt":
            return self._optimize_prompt(text)
        return text

    def _optimize_prompt(self, text):
        """Send text to LLM to compress into an AI-ready prompt."""
        try:
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": PROMPT_SYSTEM_INSTRUCTION},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
                max_tokens=256
            )
            result = response.choices[0].message.content.strip()
            return result if result else text
        except Exception as e:
            print(f"LLM Error: {e}")
            return text  # Fallback to raw text on failure

# ============================================================================
# Output Layer (Keyboard Typing + Clipboard)
# ============================================================================

class OutputLayer:
    """Outputs text via keyboard simulation (terminal-compatible) and clipboard."""

    def __init__(self):
        self._typing_tool = self._detect_typing_tool()

    def _detect_typing_tool(self):
        """Detect best available keyboard simulation tool."""
        # Priority: wtype (Wayland native) > ydotool (universal) > xdotool (X11)
        for tool in ("wtype", "ydotool", "xdotool"):
            if shutil.which(tool):
                return tool
        return None

    def output_text(self, text):
        """Type text using keyboard simulation and copy to clipboard."""
        # Always copy to clipboard as backup
        self._copy_to_clipboard(text)

        # Primary: simulate keyboard typing for terminal compatibility
        if self._typing_tool:
            # Small delay to let the user release hotkey modifiers
            time.sleep(0.15)
            typed = self._type_text(text)
            if typed:
                return True

        return True  # Clipboard copy still succeeded

    def _type_text(self, text):
        """Simulate keyboard typing using detected tool."""
        try:
            if self._typing_tool == "wtype":
                # wtype is Wayland-native, reads from arguments
                subprocess.run(
                    ["wtype", "--", text],
                    timeout=30,
                    check=True
                )
                return True
            elif self._typing_tool == "ydotool":
                subprocess.run(
                    ["ydotool", "type", "--", text],
                    timeout=30,
                    check=True
                )
                return True
            elif self._typing_tool == "xdotool":
                subprocess.run(
                    ["xdotool", "type", "--clearmodifiers", "--", text],
                    timeout=30,
                    check=True
                )
                return True
        except Exception as e:
            print(f"Typing simulation failed ({self._typing_tool}): {e}")
        return False

    def _copy_to_clipboard(self, text):
        """Copy text to system clipboard as backup."""
        # Try wl-copy (Wayland) first, then xclip, then xsel
        for cmd in (
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ):
            if shutil.which(cmd[0]):
                try:
                    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                    proc.communicate(text.encode('utf-8'))
                    return True
                except Exception:
                    continue
        return False

# ============================================================================
# Notification
# ============================================================================

def notify(message, title="Glaido"):
    """Send desktop notification."""
    try:
        subprocess.run(["notify-send", title, message], check=False)
    except Exception:
        pass

# ============================================================================
# X11 Hotkey & File Watcher
# ============================================================================

class HotkeyListener:
    def __init__(self, toggle_callback, cancel_callback=None, mode_callback=None):
        self.toggle_callback = toggle_callback
        self.cancel_callback = cancel_callback
        self.mode_callback = mode_callback
        self.display = None
        self.ctrl_pressed = False
        self.shift_pressed = False

    def _handler(self, reply):
        data = reply.data
        while len(data):
            event, data = rq.EventField(None).parse_binary_value(data, self.display.display, None, None)

            if event.type == X.KeyPress:
                keysym = self.display.keycode_to_keysym(event.detail, 0)
                if keysym in (XK.XK_Control_L, XK.XK_Control_R):
                    self.ctrl_pressed = True
                elif keysym in (XK.XK_Shift_L, XK.XK_Shift_R):
                    self.shift_pressed = True
                elif keysym == XK.XK_space and self.ctrl_pressed and self.shift_pressed:
                    self.toggle_callback()
                elif keysym == XK.XK_m and self.ctrl_pressed and self.shift_pressed:
                    if self.mode_callback:
                        self.mode_callback()
                elif keysym == XK.XK_Escape and self.cancel_callback:
                    self.cancel_callback()
            elif event.type == X.KeyRelease:
                keysym = self.display.keycode_to_keysym(event.detail, 0)
                if keysym in (XK.XK_Control_L, XK.XK_Control_R):
                    self.ctrl_pressed = False
                elif keysym in (XK.XK_Shift_L, XK.XK_Shift_R):
                    self.shift_pressed = False

    def start(self):
        self.display = Display()
        ctx = self.display.record_create_context(0, [record.AllClients], [{
            'core_requests': (0, 0), 'core_replies': (0, 0),
            'ext_requests': (0, 0, 0, 0), 'ext_replies': (0, 0, 0, 0),
            'delivered_events': (0, 0), 'device_events': (X.KeyPress, X.KeyRelease),
            'errors': (0, 0), 'client_started': False, 'client_died': False,
        }])
        self.display.record_enable_context(ctx, self._handler)
        self.display.record_free_context(ctx)

class FileWatcher:
    def __init__(self, callback):
        self.callback = callback
        self.last_mtime = 0
        self.running = False

    def start(self):
        self.running = True
        while self.running:
            try:
                if TOGGLE_FILE.exists():
                    mtime = TOGGLE_FILE.stat().st_mtime
                    if mtime > self.last_mtime:
                        self.last_mtime = mtime
                        self.callback()
            except Exception:
                pass
            time.sleep(0.1)

# ============================================================================
# Main Application
# ============================================================================

class Glaido:
    def __init__(self):
        self.recorder = AudioRecorder()
        self.ducker = AudioDucker()
        self.processor = ProcessingLayer()
        self.output = OutputLayer()
        self.hotkey = HotkeyListener(
            self.toggle, self.cancel, self.switch_mode
        ) if HAS_XLIB else None
        self.file_watcher = FileWatcher(self.toggle)

    def switch_mode(self):
        """Toggle between transcribe and prompt mode."""
        new_mode = self.processor.toggle_mode()
        label = "Transcribe" if new_mode == "transcribe" else "AI Prompt"
        print(f"Mode: {label}")
        notify(f"Mode: {label}", "Glaido")

    def toggle(self):
        if not self.recorder.is_recording:
            if self.recorder.start():
                self.ducker.mute_others()
                mode_label = "Transcribe" if self.processor.mode == "transcribe" else "AI Prompt"
                print(f"Recording started [{mode_label}]")
                notify(f"Recording started [{mode_label}]", "Glaido")
        else:
            duration = self.recorder.stop()
            self.ducker.restore()

            if duration:
                print(f"Recorded {duration:.1f}s - Processing...")
                notify("Processing...", "Glaido")

                def process_task():
                    # STT Layer
                    text = transcribe_audio()
                    if not text:
                        print("Transcription failed")
                        notify("Transcription failed", "Glaido")
                        return

                    # Processing Layer (mode switch)
                    processed = self.processor.process(text)

                    # Output Layer (type + clipboard)
                    self.output.output_text(processed)

                    preview = processed[:80]
                    mode_label = "Transcribe" if self.processor.mode == "transcribe" else "AI Prompt"
                    print(f"[{mode_label}] {preview}")
                    notify(f"[{mode_label}]\n{preview}", "Glaido")

                threading.Thread(target=process_task, daemon=True).start()

    def cancel(self):
        """Cancel recording without transcribing."""
        if self.recorder.is_recording:
            if self.recorder.cancel():
                self.ducker.restore()
                print("Recording cancelled")
                notify("Recording cancelled", "Glaido")

    def run(self):
        typing_tool = self.output._typing_tool or "clipboard-only"
        mode_label = "Transcribe" if self.processor.mode == "transcribe" else "AI Prompt"

        print("=" * 50)
        print("Glaido - Voice Transcription & AI Prompt")
        print("=" * 50)
        print(f"  Ctrl+Shift+Space  - Toggle recording")
        print(f"  Ctrl+Shift+M      - Switch mode")
        print(f"  Escape            - Cancel recording")
        print(f"  Mode: {mode_label}")
        print(f"  Output: {typing_tool}")
        print("=" * 50)

        notify(
            f"Glaido is ready!\n"
            f"Ctrl+Shift+Space to record\n"
            f"Ctrl+Shift+M to switch mode\n"
            f"Mode: {mode_label}",
            "Glaido"
        )

        # Start watchers
        threading.Thread(target=self.file_watcher.start, daemon=True).start()

        try:
            if HAS_XLIB:
                self.hotkey.start()
            else:
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\nGoodbye!")

def main():
    app = Glaido()
    app.run()

if __name__ == "__main__":
    main()
