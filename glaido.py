#!/usr/bin/env python3
"""
Glaido - Voice Transcription & AI Prompt Assistant (Background Service)

Pipeline: Hotkey -> Audio Capture -> STT -> Processing Layer -> Output Layer

Global hotkeys:
  Ctrl+Shift+Space  - Toggle recording
  Ctrl+Shift+M      - Switch mode (Transcribe / Prompt)
  Escape             - Cancel recording

Command-line options:
  --test-panel      - Test panel display without recording
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

# Import recording panel
from recording_panel import PanelWindow, PanelState

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

# System prompt for English improvement
ENGLISH_IMPROVEMENT_INSTRUCTION = (
    "You are an English language expert. Improve the following text by:\n"
    "1. Fixing grammar errors\n"
    "2. Using better vocabulary\n"
    "3. Improving sentence structure\n"
    "4. Keeping the original meaning\n"
    "\n"
    "Return ONLY the improved text, no explanations."
)

# ============================================================================
# Audio Recording
# ============================================================================


class AudioRecorder:
    def __init__(self, on_audio_level=None):
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.lock = threading.Lock()
        self.on_audio_level = on_audio_level

    def _audio_callback(self, indata, frames, time, status):
        if self.recording:
            self.audio_data.append(indata.copy())

            # Calculate RMS audio level for waveform visualization
            if self.on_audio_level:
                audio_chunk = indata.copy().flatten().astype(np.float32)
                # Convert from int16 range to float range if needed
                if audio_chunk.max() > 1.0:
                    audio_chunk = audio_chunk / 32768.0
                rms = np.sqrt(np.mean(audio_chunk**2))
                normalized = min(rms / 0.1, 1.0)  # Normalize with ceiling
                self.on_audio_level(normalized)

    def start(self):
        with self.lock:
            if self.recording:
                return False
            self.recording = True
            self.audio_data = []

        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            callback=self._audio_callback,
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
                ["pactl", "--version"], capture_output=True, timeout=2
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
                timeout=2,
            )
            if result.returncode == 0:
                sink_inputs = []
                for line in result.stdout.strip().split("\n"):
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
                    timeout=1,
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
                    timeout=1,
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
                response_format="text",
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

    def process(self, text, improve_english=False):
        """
        Process text through the current mode pipeline.

        Args:
            text: The transcribed text to process
            improve_english: If True, improve English grammar and vocabulary

        Returns:
            A dict with:
            - original: The original transcription
            - improved: The improved/processed text
            - mode: The processing mode used ("transcribe" or "prompt")
        """
        original = text
        improved = text

        if self._mode == "transcribe":
            if improve_english:
                improved = self._improve_english(text)
        elif self._mode == "prompt":
            improved = self._optimize_prompt(text)

        # Return dict format for rich output
        return {"original": original, "improved": improved, "mode": self._mode}

    def _improve_english(self, text):
        """Send text to LLM to improve English grammar and vocabulary."""
        try:
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": ENGLISH_IMPROVEMENT_INSTRUCTION},
                    {"role": "user", "content": f"Original: {text}\nImproved:"},
                ],
                temperature=0.3,
                max_tokens=512,
            )
            result = response.choices[0].message.content.strip()
            return result if result else text
        except Exception as e:
            print(f"English improvement error: {e}")
            return text  # Fallback to raw text on failure

    def _optimize_prompt(self, text):
        """Send text to LLM to compress into an AI-ready prompt."""
        try:
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": PROMPT_SYSTEM_INSTRUCTION},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
                max_tokens=256,
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
                subprocess.run(["wtype", "--", text], timeout=30, check=True)
                return True
            elif self._typing_tool == "ydotool":
                subprocess.run(["ydotool", "type", "--", text], timeout=30, check=True)
                return True
            elif self._typing_tool == "xdotool":
                subprocess.run(
                    ["xdotool", "type", "--clearmodifiers", "--", text],
                    timeout=30,
                    check=True,
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
                    proc.communicate(text.encode("utf-8"))
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
            event, data = rq.EventField(None).parse_binary_value(
                data, self.display.display, None, None
            )

            if event.type == X.KeyPress:
                keysym = self.display.keycode_to_keysym(event.detail, 0)
                if keysym in (XK.XK_Control_L, XK.XK_Control_R):
                    self.ctrl_pressed = True
                elif keysym in (XK.XK_Shift_L, XK.XK_Shift_R):
                    self.shift_pressed = True
                elif keysym == XK.XK_space and self.ctrl_pressed and self.shift_pressed:
                    print("[Hotkey] Ctrl+Shift+Space pressed - toggling recording")
                    self.toggle_callback()
                elif (
                    keysym in (XK.XK_m, XK.XK_M)
                    and self.ctrl_pressed
                    and self.shift_pressed
                ):
                    print(
                        f"[Hotkey] Ctrl+Shift+M pressed - keysym={keysym}, mode_callback={'set' if self.mode_callback else 'None'}"
                    )
                    if self.mode_callback:
                        self.mode_callback()
                elif keysym == XK.XK_Escape and self.cancel_callback:
                    print("[Hotkey] Escape pressed - cancelling recording")
                    self.cancel_callback()
            elif event.type == X.KeyRelease:
                keysym = self.display.keycode_to_keysym(event.detail, 0)
                if keysym in (XK.XK_Control_L, XK.XK_Control_R):
                    self.ctrl_pressed = False
                elif keysym in (XK.XK_Shift_L, XK.XK_Shift_R):
                    self.shift_pressed = False

    def start(self):
        self.display = Display()
        ctx = self.display.record_create_context(
            0,
            [record.AllClients],
            [
                {
                    "core_requests": (0, 0),
                    "core_replies": (0, 0),
                    "ext_requests": (0, 0, 0, 0),
                    "ext_replies": (0, 0, 0, 0),
                    "delivered_events": (0, 0),
                    "device_events": (X.KeyPress, X.KeyRelease),
                    "errors": (0, 0),
                    "client_started": False,
                    "client_died": False,
                }
            ],
        )
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
        # Panel will be created in a background thread (required by tkinter)
        self.panel = None
        self._panel_queue = None
        self._panel_thread = None

        # Start panel thread first (creates panel with proper thread ownership)
        self._start_panel_thread()

        # Initialize recorder with audio level callback
        self.recorder = AudioRecorder(on_audio_level=self._on_audio_level)
        self.ducker = AudioDucker()
        self.processor = ProcessingLayer()
        self.output = OutputLayer()
        self.hotkey = (
            HotkeyListener(self.toggle, self.cancel, self.switch_mode)
            if HAS_XLIB
            else None
        )
        self.file_watcher = FileWatcher(self.toggle)

    def _on_accept(self, improved_text: str):
        """Handle accept from review panel."""
        print("[Glaido] User accepted improved text")
        print("[Glaido] User accepted, typing text")
        if improved_text:
            self.output.output_text(improved_text)
            preview = improved_text[:80]
            print(f"[Output] {preview}")
        print("[Glaido] Text output complete")

    def _on_reject(self, original_text: str):
        """Handle reject from review panel."""
        print("[Glaido] User rejected improved text")
        print("[Glaido] User rejected, typing original text")
        if original_text:
            self.output.output_text(original_text)
            preview = original_text[:80]
            print(f"[Output] {preview}")
        print("[Glaido] Original text output complete")

    def _on_audio_level(self, level: float):
        """Forward audio level to panel for waveform visualization (thread-safe)."""
        # Debug output for audio levels (only log significant levels to avoid spam)
        # Only log significant audio levels periodically to avoid spam
        if level > 0.3:
            print(f"[Glaido] Audio level: {level:.2f}")
        if self.panel and self._panel_queue is not None:
            try:
                self._panel_queue.put(("waveform", level), block=False)
            except Exception as e:
                print(f"[Glaido] WARNING: Failed to send waveform: {e}")

    def _start_panel_thread(self):
        """Start the panel in a background thread with command queue."""
        import queue

        self._panel_queue = queue.Queue()
        self._panel_thread = threading.Thread(target=self._panel_main, daemon=True)
        self._panel_thread.start()

    def _panel_main(self):
        """Main function for panel thread - creates panel and processes commands."""
        try:
            print("[Glaido] Panel thread starting...")

            # Create panel in this thread (required by tkinter)
            self.panel = PanelWindow(
                on_accept=self._on_accept,
                on_reject=self._on_reject,
            )
            print("[Glaido] Panel created in background thread")

            # Pre-create the window (hidden) so we can use root.after() for command processing
            # This is necessary because tkinter requires window operations in the same thread
            if self.panel.root is None:
                self.panel._create_window()
                self.panel._create_recording_ui()
                self.panel._create_processing_ui()
                self.panel._create_review_ui()
                self.panel.root.withdraw()  # Hide until needed
            print("[Glaido] Panel window pre-created")

            # Start command processing loop
            self._process_panel_commands()

        except Exception as e:
            print(f"[Glaido] ERROR: Failed to create panel: {e}")
            import traceback

            traceback.print_exc()
            self.panel = None

    def _process_panel_commands(self):
        """Process commands from the queue and run tkinter mainloop."""
        import queue

        def check_queue():
            try:
                while True:
                    cmd, *args = self._panel_queue.get_nowait()
                    if cmd == "show_recording":
                        self.panel.show_recording(args[0] if args else "Dictation")
                    elif cmd == "show_processing":
                        self.panel.show_processing()
                    elif cmd == "show_review":
                        self.panel.show_review(args[0], args[1])
                    elif cmd == "hide":
                        self.panel.hide()
                    elif cmd == "update_mode":
                        self.panel.update_mode(args[0])
                    elif cmd == "waveform":
                        self.panel.update_waveform(args[0])
                    elif cmd == "destroy":
                        self.panel.destroy()
                        return
            except queue.Empty:
                pass
            # Schedule next check
            if self.panel and self.panel.root:
                self.panel.root.after(16, check_queue)  # ~60fps

        # Start the queue checker
        if self.panel and self.panel.root:
            self.panel.root.after(16, check_queue)
            print("[Glaido] Starting panel mainloop...")
            self.panel.run()

    def _panel_cmd(self, cmd, *args):
        """Send a command to the panel thread (thread-safe)."""
        if self._panel_queue is not None:
            try:
                self._panel_queue.put((cmd,) + args, block=False)
            except Exception as e:
                print(f"[Glaido] WARNING: Failed to send panel command: {e}")

    def switch_mode(self):
        """Toggle between transcribe and prompt mode."""
        old_mode = self.processor.mode
        new_mode = self.processor.toggle_mode()
        label = "Transcribe" if new_mode == "transcribe" else "AI Prompt"
        print(f"[Glaido] Mode switched: {old_mode} -> {new_mode} ({label})")

        # Update panel mode indicator if panel is visible
        if self.panel:
            print(f"[Glaido] Sending update_mode command to panel: {label}")
            self._panel_cmd("update_mode", label)

        # Show notification for user feedback (even when not recording)
        notify(f"Mode: {label}", "Glaido")

    def toggle(self):
        if not self.recorder.is_recording:
            # START RECORDING
            print("[Glaido] Recording started")
            if self.recorder.start():
                self.ducker.mute_others()
                mode_label = (
                    "Transcribe" if self.processor.mode == "transcribe" else "AI Prompt"
                )
                print(f"[Glaido] Recording started [{mode_label}]")

                # Show recording panel
                self._panel_cmd("show_recording", mode_label)
            else:
                print("[Glaido] ERROR: Failed to start recording")
        else:
            # STOP RECORDING
            print("[Glaido] Recording stopped, processing...")
            duration = self.recorder.stop()
            self.ducker.restore()

            if duration:
                print(f"[Glaido] Recorded {duration:.1f}s - Processing...")

                # Show processing state
                self._panel_cmd("show_processing")

                def process_task():
                    print("[Glaido] Starting transcription...")
                    # STT Layer
                    text = transcribe_audio()
                    if not text:
                        print("[Glaido] Transcription failed")
                        notify("Transcription failed", "Glaido")
                        self._panel_cmd("hide")
                        return

                    print(f'[Glaido] Transcription complete: "{text}"')

                    # Processing Layer (mode switch)
                    print("[Glaido] Processing text...")
                    result = self.processor.process(text, improve_english=True)
                    original = result["original"]
                    improved = result["improved"]
                    print(f"[Glaido] Processing complete")

                    # Show review panel with diff
                    print("[Glaido] Showing review panel")
                    self._panel_cmd("show_review", original, improved)

                    mode_label = (
                        "Transcribe"
                        if self.processor.mode == "transcribe"
                        else "AI Prompt"
                    )
                    print(f"[Glaido] [{mode_label}] Reviewing improvements...")

                threading.Thread(target=process_task, daemon=True).start()

    def cancel(self):
        """Cancel recording without transcribing."""
        if self.recorder.is_recording:
            if self.recorder.cancel():
                self.ducker.restore()
                print("Recording cancelled")
                # Hide the panel
                self._panel_cmd("hide")

    def run(self):
        typing_tool = self.output._typing_tool or "clipboard-only"
        mode_label = (
            "Transcribe" if self.processor.mode == "transcribe" else "AI Prompt"
        )
        panel_status = "enabled" if self.panel else "disabled (error)"

        print("=" * 50)
        print("Glaido - Voice Transcription & AI Prompt")
        print("=" * 50)
        print(f"  Ctrl+Shift+Space  - Toggle recording")
        print(f"  Ctrl+Shift+M      - Switch mode (current: {mode_label})")
        print(f"  Escape            - Cancel recording")
        print(f"  Output: {typing_tool}")
        print(f"  Panel: {panel_status}")
        print("-" * 50)
        print(f"  Run with --test-panel to test the panel UI")
        print("=" * 50)

        # Only show startup notification, rest is via panel
        notify(
            f"Glaido is ready!\n"
            f"Ctrl+Shift+Space to record\n"
            f"Ctrl+Shift+M to switch mode",
            "Glaido",
        )

        # Start file watcher in background
        threading.Thread(target=self.file_watcher.start, daemon=True).start()

        try:
            if HAS_XLIB and self.hotkey:
                # Run hotkey listener in separate thread to avoid blocking
                hotkey_thread = threading.Thread(target=self.hotkey.start, daemon=True)
                hotkey_thread.start()
                print("[Glaido] Hotkey listener started")

                # Keep main thread alive
                while True:
                    time.sleep(1)
            else:
                print("[Glaido] Running in file-watcher only mode")
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            self._panel_cmd("destroy")


def test_panel_mode():
    """Test mode: just show the panel without recording."""
    print("=" * 50)
    print("Glaido - Panel Test Mode")
    print("=" * 50)
    print("Testing panel display...")
    print("Press Ctrl+C to exit")
    print("=" * 50)

    # Create panel in main thread for testing
    from recording_panel import PanelWindow, PanelState
    import math

    panel = None
    test_step = [0]  # Use list to allow mutation in nested function

    def on_accept(text):
        print(f"[Test] Accepted: {text[:50]}...")

    def on_reject(text):
        print(f"[Test] Rejected: {text[:50]}...")

    def run_test_step():
        """Run each test step using tkinter's after() to keep UI responsive."""
        step = test_step[0]

        if step == 0:
            # Show recording panel
            print("[Test] Showing recording panel...")
            panel.show_recording("AI Prompt")
            test_step[0] = 1
            panel.root.after(2000, run_test_step)  # Wait 2 seconds

        elif step == 1:
            # Show processing panel
            print("[Test] Showing processing panel...")
            panel.show_processing()
            test_step[0] = 2
            panel.root.after(2000, run_test_step)

        elif step == 2:
            # Show review panel
            print("[Test] Showing review panel...")
            panel.show_review(
                "This is the original transcribed text.",
                "This is the improved AI-processed text.",
            )
            test_step[0] = 3
            panel.root.after(2000, run_test_step)

        elif step == 3:
            # Start waveform animation
            print("[Test] Testing waveform animation...")
            test_step[0] = 4
            animate_waveform(0)

        elif step == 4:
            # Hide panel and finish
            print("[Test] Hiding panel...")
            panel.hide()
            test_step[0] = 5
            panel.root.after(1000, run_test_step)

        elif step == 5:
            # Test complete
            print("[Test] Panel test complete!")
            panel.destroy()

    def animate_waveform(i):
        """Animate waveform for 2 seconds (60 frames at ~30fps)."""
        if i < 60 and test_step[0] == 4:
            level = 0.3 + 0.4 * math.sin(i * 0.3)  # Oscillating level
            panel.update_waveform(level)
            panel.root.after(33, lambda: animate_waveform(i + 1))  # ~30fps
        elif test_step[0] == 4:
            # Animation done, move to next step
            run_test_step()

    try:
        panel = PanelWindow(on_accept=on_accept, on_reject=on_reject)
        panel._create_window()
        panel._create_recording_ui()
        panel._create_processing_ui()
        panel._create_review_ui()

        # Start the test sequence
        run_test_step()

        # Run the tkinter mainloop (this blocks until window is closed)
        print("[Test] Starting panel mainloop...")
        panel.run()

    except KeyboardInterrupt:
        print("\n[Test] Interrupted by user")
        if panel:
            panel.destroy()
    except Exception as e:
        print(f"[Test] ERROR: {e}")
        import traceback

        traceback.print_exc()
        if panel:
            panel.destroy()


def main():
    # Check for --test-panel flag
    if "--test-panel" in sys.argv:
        test_panel_mode()
        return

    app = Glaido()
    app.run()


if __name__ == "__main__":
    main()
