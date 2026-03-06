"""
Glider Recording Panel - Floating UI for recording and review states.

Features:
- Smooth animated transitions between states
- Fade in/out effects
- Rounded corners with translucent background
- Horizontal layout with separators
- Auto-dismiss in review state
- Polished visual design with consistent spacing
"""

import tkinter as tk
from tkinter import ttk
from enum import Enum, auto
import math
import difflib
import re
import platform


class PanelState(Enum):
    """Enum representing the different panel states."""

    HIDDEN = auto()
    RECORDING = auto()
    PROCESSING = auto()
    REVIEW = auto()


class PanelWindow:
    """
    A floating, borderless, always-on-top window for recording and review UI.

    Supports three states:
    - HIDDEN: Window not visible
    - RECORDING: Small floating panel with timer and waveform
    - REVIEW: Expanded panel with original/improved text comparison

    Features smooth animations, rounded corners, and auto-dismiss.
    """

    # ── Dimensions ──
    RECORDING_WIDTH = 320
    RECORDING_HEIGHT = 58
    REVIEW_WIDTH = 540
    REVIEW_HEIGHT = 420
    BOTTOM_MARGIN = 50
    BORDER_RADIUS = 29  # Full capsule for recording pill

    # ── Animation ──
    FADE_DURATION = 150
    FADE_STEPS = 10
    TRANSITION_DURATION = 200
    TRANSITION_STEPS = 12
    PULSE_DURATION = 1200  # ms per pulse cycle

    # ── Auto-dismiss ──
    AUTO_DISMISS_DELAY = 8000

    # ── Color palette (WhisperFlow dark) ──
    BG_COLOR = "#0d0d0e"
    SURFACE_COLOR = "#17171a"
    BORDER_COLOR_HEX = "#2a2a2f"
    FG_COLOR = "#f5f5f7"
    FG_SECONDARY = "#86868b"
    ACCENT_COLOR = "#8b5cf6"       # Violet
    ACCENT_GLOW = "#a78bfa"        # Lighter violet (waveform peaks)
    SECONDARY_BG = "#17171a"
    RECORDING_DOT_COLOR = "#ef4444"
    RECORDING_DOT_SIZE = 10
    WAVE_COLOR = "#8b5cf6"
    WAVE_ACTIVE = "#a78bfa"
    ADD_COLOR = "#34d399"          # Emerald (diff: added)
    DEL_COLOR = "#f87171"          # Red (diff: removed)

    # ── Compatibility aliases for unreplaced code ──
    WAVE_COLOR_HIGH = "#a78bfa"    # maps to ACCENT_GLOW until _draw_waveform replaced
    SUGGESTION_BG = "#17171a"      # maps to SURFACE_COLOR until _create_review_ui replaced
    BUTTON_ACCEPT = "#34d399"      # maps to ADD_COLOR until _create_review_ui replaced
    BUTTON_REJECT = "#f87171"      # maps to DEL_COLOR until _create_review_ui replaced
    BORDER_COLOR = "#2a2a2f"       # maps to BORDER_COLOR_HEX for _on_resize
    TIMER_COLOR = "#f5f5f7"        # maps to FG_COLOR until _create_recording_ui replaced
    MODE_BG_COLOR = "#17171a"      # maps to SURFACE_COLOR until _create_recording_ui replaced
    TRANSPARENT_COLOR = "#010101"  # Linux transparency hack — kept until _create_window replaced

    # ── Typography ──
    FONT_PRIMARY = ("Inter", "SF Pro Display", "Helvetica Neue", "Arial", "sans-serif")
    FONT_MONO = ("JetBrains Mono", "SF Mono", "Consolas", "Monaco", "monospace")

    def __init__(self, on_accept=None, on_reject=None):
        """
        Initialize the panel window.

        Args:
            on_accept: Callback when user accepts improved text. Receives improved text.
            on_reject: Callback when user rejects improved text. Receives original text.
        """
        self.root = None
        self.state = PanelState.HIDDEN
        self.timer_seconds = 0
        self.timer_job = None
        self.pulse_job = None
        self.pulse_state = 0

        # Auto-dismiss tracking
        self._auto_dismiss_job = None
        self._is_hovered = False

        # Animation tracking
        self._fade_job = None
        self._transition_job = None
        self._current_alpha = 0.0
        self._target_alpha = 0.85  # Translucent (0.85 per design)
        self._current_geometry = None
        self._target_geometry = None

        # Canvas for rounded corners
        self._canvas = None
        self._canvas_bg_id = None

        # Callbacks
        self.on_accept = on_accept
        self.on_reject = on_reject

        # Stored text for callbacks
        self._original_text = ""
        self._improved_text = ""
        self._mode_name = "Dictation"

        # Audio tracking
        self._last_audio_time = 0
        self._has_audio_data = False

        # Widget references
        self.recording_frame = None
        self.review_frame = None
        self.processing_frame = None
        self._spinner_canvas = None
        self._spinner_angle = 0
        self.timer_label = None
        self.mode_label = None
        self.mode_capsule = None
        self.indicator_canvas = None   # compat alias — old _start_pulse_animation checks this
        self.recording_indicator = None
        self.recording_dot = None
        self.waveform_canvas = None
        self.original_text = None
        self.improved_text = None
        self.suggestions_text = None
        self.title_label = None
        self.content_container = None

    def _get_font(self, font_type="primary", size=12, weight="normal"):
        """Return a tkinter font tuple: (family, size) or (family, size, style)."""
        if font_type == "mono":
            if weight and weight != "normal":
                return (self.FONT_MONO[0], size, weight)
            return (self.FONT_MONO[0], size)
        if weight and weight != "normal":
            return (self.FONT_PRIMARY[0], size, weight)
        return (self.FONT_PRIMARY[0], size)

    def _get_widget_bg(self):
        """Get the appropriate background color for widgets."""
        # Use transparent color on Linux to match the rounded corner mask
        if getattr(self, "_use_transparent_color", False):
            return self.TRANSPARENT_COLOR
        return self.BG_COLOR

    def _create_window(self):
        """Create the main window with borderless, always-on-top settings."""
        self.root = tk.Tk()
        self.root.overrideredirect(True)  # Remove window decorations
        self.root.wm_attributes("-topmost", True)  # Always on top

        # Check if we're on Linux
        self._is_linux = platform.system() == "Linux"

        # Initialize transparency - use different approaches for Linux vs other platforms
        if self._is_linux:
            # On Linux, use transparent color for rounded corners
            try:
                self.root.wm_attributes("-transparentcolor", self.TRANSPARENT_COLOR)
                self._use_transparent_color = True
            except tk.TclError:
                self._use_transparent_color = False

            # Also set alpha for overall transparency
            try:
                self.root.wm_attributes("-alpha", 0.0)
                self._current_alpha = 0.0
            except tk.TclError:
                self._current_alpha = 0.85
        else:
            # On other platforms, just use alpha
            self._use_transparent_color = False
            try:
                self.root.wm_attributes("-alpha", 0.0)
                self._current_alpha = 0.0
            except tk.TclError:
                self._current_alpha = 0.85

        # Try to enable compositor shadow hint (Linux)
        try:
            self.root.attributes("-type", "dock")
        except tk.TclError:
            pass

        # Bind keyboard shortcuts
        self.root.bind("<Return>", lambda e: self._on_accept())
        self.root.bind("<Escape>", lambda e: self._on_reject())

        # Create the rounded corner canvas container
        self._create_rounded_container()

    def _create_rounded_container(self):
        """Create a canvas with rounded rectangle for the window background."""
        # On Linux with transparent color support, use the special color for corners
        canvas_bg = (
            self.TRANSPARENT_COLOR if self._use_transparent_color else self.BG_COLOR
        )

        # Create canvas for rounded corners
        self._canvas = tk.Canvas(
            self.root,
            bg=canvas_bg,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Create content container inside canvas
        # On Linux, content also needs transparent color background
        content_bg = (
            self.TRANSPARENT_COLOR if self._use_transparent_color else self.BG_COLOR
        )
        self.content_container = tk.Frame(self._canvas, bg=content_bg)

        # Bind to resize events to redraw rounded rectangle
        self.root.bind("<Configure>", self._on_resize)

    def _on_resize(self, event=None):
        """Redraw the rounded rectangle background on resize."""
        if not self._canvas:
            return

        # Clear canvas
        self._canvas.delete("all")

        # Get current dimensions
        width = self._canvas.winfo_width()
        height = self._canvas.winfo_height()

        if width <= 1 or height <= 1:
            # Not yet rendered, schedule redraw
            if self.root:
                self.root.after(50, self._on_resize)
            return

        # Draw rounded rectangle background
        radius = self.BORDER_RADIUS

        # When using transparent color, the canvas background is already the transparent color
        # So we just draw the rounded rectangle with the actual background color
        if self._use_transparent_color:
            # Draw the rounded rectangle with background color - corners stay transparent
            self._draw_rounded_rect(
                0, 0, width, height, radius, fill=self.BG_COLOR, outline=""
            )
        else:
            # 1px border layer
            self._draw_rounded_rect(
                0, 0, width, height, radius,
                fill=self.BORDER_COLOR_HEX, outline=""
            )
            # Main background (inset 1px so border shows)
            self._draw_rounded_rect(
                1, 1, width - 1, height - 1, max(radius - 1, 0),
                fill=self.BG_COLOR, outline=""
            )

        # Position the content container frame inside the rounded rectangle
        # Account for the border radius to keep content inside rounded corners
        inset = radius // 2
        self.content_container.place(
            x=inset, y=4, width=width - 2 * inset, height=height - 8
        )
        self._canvas.update_idletasks()

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Draw a rounded rectangle using a smooth polygon."""
        max_radius = min((x2 - x1) // 2, (y2 - y1) // 2)
        radius = min(radius, max_radius)

        if radius < 1:
            return self._canvas.create_rectangle(x1, y1, x2, y2, **kwargs)

        # 12-point smooth polygon gives natural rounded corners in tkinter
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self._canvas.create_polygon(points, smooth=True, **kwargs)

    def _get_screen_center_x(self, width: int) -> int:
        """Calculate X position for centered window."""
        screen_width = self.root.winfo_screenwidth()
        return (screen_width - width) // 2

    def _get_screen_bottom_y(self, height: int) -> int:
        """Calculate Y position for bottom-aligned window."""
        screen_height = self.root.winfo_screenheight()
        return screen_height - height - self.BOTTOM_MARGIN

    def _position_window(self, width: int, height: int, animate: bool = False):
        """Position window at bottom-center of screen with optional animation."""
        x = self._get_screen_center_x(width)
        y = self._get_screen_bottom_y(height)

        if animate and self._current_geometry:
            # Parse current geometry
            current = self._parse_geometry(self._current_geometry)
            target = {"x": x, "y": y, "width": width, "height": height}
            self._animate_transition(current, target)
        else:
            self.root.geometry(f"{width}x{height}+{x}+{y}")
            self._current_geometry = f"{width}x{height}+{x}+{y}"
            # Redraw rounded corners after position set
            self.root.after(10, self._on_resize)

    def _parse_geometry(self, geom: str) -> dict:
        """Parse geometry string into dict."""
        # Format: WxH+X+Y
        parts = geom.replace("+", "x").split("x")
        return {
            "width": int(parts[0]),
            "height": int(parts[1]),
            "x": int(parts[2]),
            "y": int(parts[3]),
        }

    def _animate_transition(self, start: dict, end: dict):
        """Animate window geometry transition."""
        step = 0
        total_steps = self.TRANSITION_STEPS
        duration_per_step = self.TRANSITION_DURATION // total_steps

        def update_frame():
            nonlocal step
            step += 1
            progress = step / total_steps

            # Ease out cubic
            ease = 1 - (1 - progress) ** 3

            # Interpolate values
            width = int(start["width"] + (end["width"] - start["width"]) * ease)
            height = int(start["height"] + (end["height"] - start["height"]) * ease)
            x = int(start["x"] + (end["x"] - start["x"]) * ease)
            y = int(start["y"] + (end["y"] - start["y"]) * ease)

            self.root.geometry(f"{width}x{height}+{x}+{y}")
            self._current_geometry = f"{width}x{height}+{x}+{y}"

            # Redraw rounded corners
            self._on_resize()

            if step < total_steps:
                self._transition_job = self.root.after(duration_per_step, update_frame)

        update_frame()

    def _fade_in(self, callback=None):
        """Fade window from 0 to target alpha."""
        self._cancel_fade()
        step = 0
        total_steps = self.FADE_STEPS
        duration_per_step = self.FADE_DURATION // total_steps
        alpha_step = self._target_alpha / total_steps

        def update_alpha():
            nonlocal step
            step += 1

            self._current_alpha = min(alpha_step * step, self._target_alpha)
            try:
                self.root.wm_attributes("-alpha", self._current_alpha)
            except tk.TclError:
                pass

            if step < total_steps:
                self._fade_job = self.root.after(duration_per_step, update_alpha)
            elif callback:
                callback()

        update_alpha()

    def _fade_out(self, callback=None):
        """Fade window from current alpha to 0."""
        self._cancel_fade()
        step = 0
        total_steps = self.FADE_STEPS
        duration_per_step = self.FADE_DURATION // total_steps
        start_alpha = self._current_alpha
        alpha_step = start_alpha / total_steps

        def update_alpha():
            nonlocal step
            step += 1

            self._current_alpha = max(start_alpha - alpha_step * step, 0.0)
            try:
                self.root.wm_attributes("-alpha", self._current_alpha)
            except tk.TclError:
                pass

            if step < total_steps:
                self._fade_job = self.root.after(duration_per_step, update_alpha)
            elif callback:
                callback()

        update_alpha()

    def _cancel_fade(self):
        """Cancel any ongoing fade animation."""
        if self._fade_job:
            self.root.after_cancel(self._fade_job)
            self._fade_job = None

    def _cancel_transition(self):
        """Cancel any ongoing transition animation."""
        if self._transition_job:
            self.root.after_cancel(self._transition_job)
            self._transition_job = None

    def _create_separator(self, parent, height=24):
        """Create a vertical separator line."""
        separator = tk.Frame(
            parent,
            bg="#333333",  # Subtle separator color
            width=1,
            height=height,
        )
        return separator

    def _create_recording_ui(self):
        """WhisperFlow-style compact recording capsule."""
        widget_bg = self.BG_COLOR
        self.recording_frame = tk.Frame(self.content_container, bg=widget_bg)

        # ── Left: pulsing red dot ──
        left = tk.Frame(self.recording_frame, bg=widget_bg)
        left.pack(side=tk.LEFT, padx=(8, 4))

        self.recording_indicator = tk.Canvas(
            left,
            width=self.RECORDING_DOT_SIZE + 2,
            height=self.RECORDING_DOT_SIZE + 2,
            bg=widget_bg,
            highlightthickness=0,
        )
        self.recording_indicator.pack(side=tk.LEFT)
        self.recording_dot = self.recording_indicator.create_oval(
            1, 1,
            self.RECORDING_DOT_SIZE + 1,
            self.RECORDING_DOT_SIZE + 1,
            fill=self.RECORDING_DOT_COLOR,
            outline="",
        )

        # ── Center: waveform ──
        wave_frame = tk.Frame(self.recording_frame, bg=widget_bg)
        wave_frame.pack(side=tk.LEFT, padx=6, expand=True, fill=tk.X)

        self.waveform_canvas = tk.Canvas(
            wave_frame,
            width=160,
            height=30,
            bg=widget_bg,
            highlightthickness=0,
        )
        self.waveform_canvas.pack()
        self._draw_waveform(0.0)

        # ── Right: timer + mode pill ──
        right = tk.Frame(self.recording_frame, bg=widget_bg)
        right.pack(side=tk.RIGHT, padx=(4, 10))

        self.timer_label = tk.Label(
            right,
            text="00:00",
            font=self._get_font("mono", 12),
            bg=widget_bg,
            fg=self.FG_COLOR,
        )
        self.timer_label.pack(side=tk.LEFT, padx=(0, 6))

        self.mode_label = tk.Label(
            right,
            text=self._mode_name,
            font=self._get_font("primary", 9),
            bg=self.SURFACE_COLOR,
            fg=self.ACCENT_COLOR,
            padx=8,
            pady=3,
        )
        self.mode_label.pack(side=tk.LEFT)

    def _create_processing_ui(self):
        """Processing state: spinning arc + animated dots label."""
        widget_bg = self.BG_COLOR
        self.processing_frame = tk.Frame(self.content_container, bg=widget_bg)

        row = tk.Frame(self.processing_frame, bg=widget_bg)
        row.pack(expand=True)

        # Arc spinner canvas
        self._spinner_canvas = tk.Canvas(
            row, width=20, height=20, bg=widget_bg, highlightthickness=0
        )
        self._spinner_canvas.pack(side=tk.LEFT, padx=(0, 8))
        self._spinner_angle = 0

        self.processing_label = tk.Label(
            row,
            text="transcribing",
            font=self._get_font("primary", 13),
            bg=widget_bg,
            fg=self.FG_SECONDARY,
        )
        self.processing_label.pack(side=tk.LEFT)

        self._animate_processing()

    def _animate_processing(self):
        """Rotate spinner arc and cycle dots on label."""
        if self.state != PanelState.PROCESSING or not self.processing_label:
            return

        # Rotate arc by 15 deg per frame (~90 deg/s at 16fps)
        self._spinner_angle = (self._spinner_angle + 15) % 360
        self._spinner_canvas.delete("all")
        start = self._spinner_angle
        self._spinner_canvas.create_arc(
            2, 2, 18, 18,
            start=start,
            extent=270,
            outline=self.ACCENT_COLOR,
            width=2,
            style="arc",
        )

        # Cycle dots: "" → "." → ".." → "..."
        base = "transcribing"
        dots = ["", ".", "..", "..."]
        current = self.processing_label.cget("text")
        dot_count = len(current) - len(base)
        next_dots = dots[(dot_count + 1) % 4]
        self.processing_label.config(text=base + next_dots)

        if self.root:
            self.root.after(110, self._animate_processing)

    def _create_review_ui(self):
        """WhisperFlow review card: inline diff + keyboard hints."""
        widget_bg = self.BG_COLOR
        self.review_frame = tk.Frame(self.content_container, bg=widget_bg)

        # ── Section label: Original ──
        tk.Label(
            self.review_frame,
            text="Original",
            font=self._get_font("primary", 10),
            bg=widget_bg,
            fg=self.FG_SECONDARY,
        ).pack(anchor=tk.W, padx=16, pady=(14, 2))

        # Original text widget — shows diff inline
        self.original_text = tk.Text(
            self.review_frame,
            height=4,
            wrap=tk.WORD,
            font=self._get_font("primary", 12),
            bg=self.SURFACE_COLOR,
            fg=self.FG_COLOR,
            relief=tk.FLAT,
            padx=12,
            pady=8,
            highlightthickness=0,
            state=tk.DISABLED,
            cursor="arrow",
        )
        self.original_text.pack(fill=tk.X, padx=16)

        # Configure diff tags
        self.original_text.tag_configure(
            "del", foreground=self.DEL_COLOR, overstrike=True
        )
        self.original_text.tag_configure(
            "add", foreground=self.ADD_COLOR, font=self._get_font("primary", 12, "bold")
        )

        # Divider
        tk.Frame(self.review_frame, bg=self.BORDER_COLOR_HEX, height=1).pack(
            fill=tk.X, padx=16, pady=10
        )

        # ── Section label: Improved ──
        improved_header = tk.Frame(self.review_frame, bg=widget_bg)
        improved_header.pack(fill=tk.X, padx=16, pady=(0, 2))

        tk.Label(
            improved_header,
            text="Improved",
            font=self._get_font("primary", 10),
            bg=widget_bg,
            fg=self.ACCENT_COLOR,
        ).pack(side=tk.LEFT)

        tk.Label(
            improved_header,
            text="✦",
            font=self._get_font("primary", 10),
            bg=widget_bg,
            fg=self.ACCENT_GLOW,
        ).pack(side=tk.LEFT, padx=(4, 0))

        # Improved text — editable
        self.improved_text = tk.Text(
            self.review_frame,
            height=5,
            wrap=tk.WORD,
            font=self._get_font("primary", 12),
            bg=self.SURFACE_COLOR,
            fg=self.FG_COLOR,
            relief=tk.FLAT,
            padx=12,
            pady=8,
            highlightthickness=0,
            insertbackground=self.ACCENT_COLOR,
        )
        self.improved_text.pack(fill=tk.BOTH, expand=True, padx=16)

        # Divider
        tk.Frame(self.review_frame, bg=self.BORDER_COLOR_HEX, height=1).pack(
            fill=tk.X, padx=16, pady=10
        )

        # ── Keyboard hints (right-aligned) ──
        hint_frame = tk.Frame(self.review_frame, bg=widget_bg)
        hint_frame.pack(fill=tk.X, padx=16, pady=(0, 14))

        tk.Label(
            hint_frame,
            text="↵ Accept  ·  ⎋ Dismiss",
            font=self._get_font("mono", 10),
            bg=widget_bg,
            fg=self.FG_SECONDARY,
        ).pack(side=tk.RIGHT)

    def _on_review_enter(self, event=None):
        """Handle mouse enter on review panel - cancel auto-dismiss."""
        self._is_hovered = True
        self._cancel_auto_dismiss()

    def _on_review_leave(self, event=None):
        """Handle mouse leave on review panel - start auto-dismiss countdown."""
        self._is_hovered = False
        self._start_auto_dismiss()

    def _start_auto_dismiss(self):
        """Start the auto-dismiss timer for review state."""
        if self.state != PanelState.REVIEW:
            return

        self._cancel_auto_dismiss()
        self._auto_dismiss_job = self.root.after(
            self.AUTO_DISMISS_DELAY, self._auto_dismiss
        )

    def _cancel_auto_dismiss(self):
        """Cancel the auto-dismiss timer."""
        if self._auto_dismiss_job:
            self.root.after_cancel(self._auto_dismiss_job)
            self._auto_dismiss_job = None

    def _auto_dismiss(self):
        """Auto-dismiss the review panel (acts as reject)."""
        if self.state == PanelState.REVIEW and not self._is_hovered:
            print("[Panel] Auto-dismissing review panel")
            self._on_reject()

    def _compute_diff(self, original: str, improved: str):
        """
        Compute word-level diff between original and improved text.

        Returns:
            List of (tag, text) tuples where tag is None, 'added', or 'removed'
        """
        # Split into words while preserving whitespace
        original_words = re.findall(r"\S+|\s+", original)
        improved_words = re.findall(r"\S+|\s+", improved)

        # Use SequenceMatcher for word-level diff
        sm = difflib.SequenceMatcher(None, original_words, improved_words)
        diff_result = []

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                # No change
                diff_result.append((None, "".join(improved_words[j1:j2])))
            elif tag == "replace":
                # Words were replaced (show as deletion then addition)
                removed = "".join(original_words[i1:i2])
                added = "".join(improved_words[j1:j2])
                if removed.strip():
                    diff_result.append(("removed", removed))
                if added.strip():
                    diff_result.append(("added", added))
            elif tag == "delete":
                # Words were removed
                removed = "".join(original_words[i1:i2])
                if removed.strip():
                    diff_result.append(("removed", removed))
            elif tag == "insert":
                # Words were added
                added = "".join(improved_words[j1:j2])
                if added.strip():
                    diff_result.append(("added", added))

        return diff_result

    def _compute_word_diff(self, original: str, improved: str) -> list:
        """
        Compute word-level diff between original and improved text.

        Returns list of (tag, text) tuples where tag is:
          'equal' — unchanged word(s)
          'del'   — word(s) in original but not improved (show strikethrough)
          'add'   — word(s) in improved but not original (show bold emerald)
        """
        orig_words = original.split()
        impr_words = improved.split()
        matcher = difflib.SequenceMatcher(None, orig_words, impr_words)
        result = []
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                result.append(("equal", " ".join(orig_words[i1:i2])))
            elif op == "delete":
                result.append(("del", " ".join(orig_words[i1:i2])))
            elif op == "insert":
                result.append(("add", " ".join(impr_words[j1:j2])))
            elif op == "replace":
                result.append(("del", " ".join(orig_words[i1:i2])))
                result.append(("add", " ".join(impr_words[j1:j2])))
        return result

    def _extract_suggestions(self, original: str, improved: str) -> list:
        """
        Extract key improvement suggestions from the diff.

        Returns:
            List of suggestion strings like "'i think' → 'I believe'"
        """
        suggestions = []

        # Split into words
        original_words = re.findall(r"\S+|\s+", original)
        improved_words = re.findall(r"\S+|\s+", improved)

        # Use SequenceMatcher
        sm = difflib.SequenceMatcher(None, original_words, improved_words)

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace":
                old_phrase = "".join(original_words[i1:i2]).strip()
                new_phrase = "".join(improved_words[j1:j2]).strip()
                if old_phrase and new_phrase and len(old_phrase) > 2:
                    suggestions.append(f"'{old_phrase}' → '{new_phrase}'")

        # Limit to top suggestions
        return suggestions[:4]

    def _insert_highlighted_text(self, text_widget, diff_result):
        """Insert text with diff highlighting into the text widget."""
        text_widget.config(state=tk.NORMAL)
        text_widget.delete("1.0", tk.END)

        for tag, text in diff_result:
            if tag:
                text_widget.insert(tk.END, text, tag)
            else:
                text_widget.insert(tk.END, text)

        text_widget.config(state=tk.DISABLED)

    def _on_accept(self):
        """Handle accept button click or Enter key."""
        if self.state != PanelState.REVIEW:
            return

        print("[Panel] Accept clicked")
        self._cancel_auto_dismiss()

        def after_fade():
            if self.on_accept:
                self.on_accept(self._improved_text)
            self._do_hide()

        self._fade_out(callback=after_fade)

    def _on_reject(self):
        """Handle reject button click or Escape key."""
        if self.state != PanelState.REVIEW:
            return

        print("[Panel] Reject clicked")
        self._cancel_auto_dismiss()

        def after_fade():
            if self.on_reject:
                self.on_reject(self._original_text)
            self._do_hide()

        self._fade_out(callback=after_fade)

    def _do_hide(self):
        """Actually hide the window after fade out."""
        if self.root:
            self.root.withdraw()
        self._stop_timer()
        self._stop_pulse_animation()
        self._cancel_auto_dismiss()
        self.state = PanelState.HIDDEN

    def _draw_waveform(self, audio_level: float):
        """WhisperFlow-style violet bar waveform."""
        if not self.waveform_canvas:
            return
        self.waveform_canvas.delete("all")

        width = 160
        height = 30
        center_y = height // 2
        num_bars = 20
        bar_width = 3
        gap = 2
        total = num_bars * (bar_width + gap) - gap
        start_x = (width - total) // 2

        for i in range(num_bars):
            dist = abs(i - num_bars / 2) / (num_bars / 2)
            # Breathing baseline
            breathing = 0.5 + 0.5 * math.sin(self.pulse_state * 0.8 + i * 0.4)
            base_h = 2 + 3 * breathing * (1 - dist * 0.5)
            # Audio reactivity — center bars taller
            level_h = audio_level * 20 * (1.0 - dist * 0.6)
            h = max(2, base_h + level_h)

            x = start_x + i * (bar_width + gap)
            # Peaks glow brighter
            color = self.ACCENT_GLOW if (audio_level > 0.5 and dist < 0.4) else self.WAVE_COLOR

            y1 = center_y - h / 2
            y2 = center_y + h / 2
            self.waveform_canvas.create_rectangle(
                x, y1, x + bar_width, y2,
                fill=color, outline="",
            )

    def _start_pulse_animation(self):
        """Smooth pulse: dot opacity + waveform breathing at 30fps."""
        if self.state != PanelState.RECORDING:
            return

        self.pulse_state += 0.05  # ~30fps tick at 33ms interval

        # Dot: sine-driven color between dim red and full red
        alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(self.pulse_state * 1.2))
        r = int(239 * alpha)
        g = int(68 * alpha)
        b = int(68 * alpha)
        color = f"#{r:02x}{g:02x}{b:02x}"
        if hasattr(self, "recording_dot") and self.recording_indicator:
            self.recording_indicator.itemconfig(self.recording_dot, fill=color)

        # Waveform: only animate if no recent audio
        if self.waveform_canvas:
            import time as _time
            if _time.time() - self._last_audio_time > 0.1 or not self._has_audio_data:
                self._draw_waveform(0.0)  # breathing at rest

        self.pulse_job = self.root.after(33, self._start_pulse_animation)  # ~30fps

    def _stop_pulse_animation(self):
        """Stop the pulse animation."""
        if self.pulse_job:
            self.root.after_cancel(self.pulse_job)
            self.pulse_job = None

    def _update_timer(self):
        """Update the timer display."""
        if self.state != PanelState.RECORDING:
            return

        self.timer_seconds += 1
        self.set_timer(self.timer_seconds)
        self.timer_job = self.root.after(1000, self._update_timer)

    def _stop_timer(self):
        """Stop the timer updates."""
        if self.timer_job:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None

    def show_recording(self, mode_name: str = "Dictation"):
        """
        Show the recording panel in compact mode with fade-in animation.

        Args:
            mode_name: The recording mode to display (e.g., "Dictation", "Prompt")
        """
        self._mode_name = mode_name

        if self.root is None:
            self._create_window()
            self._create_recording_ui()
            self._create_processing_ui()
            self._create_review_ui()

        # Stop any existing timer/animations
        self._cancel_transition()
        self._stop_timer()
        self._stop_pulse_animation()
        self._cancel_auto_dismiss()
        self.timer_seconds = 0

        # Reset audio tracking flags
        self._has_audio_data = False
        self._last_audio_time = 0

        # Hide all frames first
        self.recording_frame.pack_forget()
        self.processing_frame.pack_forget()
        self.review_frame.pack_forget()

        # Show recording frame
        self.state = PanelState.RECORDING
        self.recording_frame.pack(fill=tk.BOTH, expand=True)

        # Update mode label (now without "MODE: " prefix)
        if self.mode_label:
            self.mode_label.config(text=mode_name)

        # Position and show window
        self._position_window(self.RECORDING_WIDTH, self.RECORDING_HEIGHT)
        self.root.deiconify()
        self.root.lift()

        # Fade in
        self._fade_in()

        # Start animations
        self._start_pulse_animation()
        self._update_timer()

    def show_processing(self):
        """Show the processing state while transcription/improvement is happening."""
        if self.root is None:
            return

        # Stop recording animations
        self._stop_timer()
        self._stop_pulse_animation()
        self._cancel_auto_dismiss()

        # Hide all frames first
        self.recording_frame.pack_forget()
        self.processing_frame.pack_forget()
        self.review_frame.pack_forget()

        # Show processing frame
        self.state = PanelState.PROCESSING
        self.processing_frame.pack(fill=tk.BOTH, expand=True)

        # Position and show window
        self._position_window(self.RECORDING_WIDTH, self.RECORDING_HEIGHT)
        self.root.deiconify()
        self.root.lift()

    def update_waveform(self, audio_level: float):
        """
        Update the waveform visualization with real audio data.

        Args:
            audio_level: Float between 0.0 and 1.0 representing audio amplitude
        """
        import time as _time

        if self.state != PanelState.RECORDING or self.waveform_canvas is None:
            return

        # Track that we received audio data
        self._last_audio_time = _time.time()
        self._has_audio_data = True

        # Clamp audio level
        audio_level = max(0.0, min(1.0, audio_level))
        self._draw_waveform(audio_level)

    def set_timer(self, seconds: int):
        """
        Update the recording timer display.

        Args:
            seconds: Number of seconds to display
        """
        minutes = seconds // 60
        secs = seconds % 60
        formatted = f"{minutes:02d}:{secs:02d}"

        if self.timer_label:
            self.timer_label.config(text=formatted)

    def update_mode(self, mode_name: str):
        """
        Update the mode label display.

        Args:
            mode_name: The mode to display (e.g., "Dictation", "Prompt")
        """
        print(f"[Panel] update_mode called with: {mode_name}")
        self._mode_name = mode_name
        if self.mode_label:
            self.mode_label.config(text=mode_name)  # Without "MODE: " prefix
            print(f"[Panel] Mode label updated to: {mode_name}")
        else:
            print(f"[Panel] Mode label not available (panel may not be initialized)")

    def show_review(self, original: str, improved: str):
        """Show the review panel with inline word diff."""
        if self.root is None:
            self._create_window()
            self._create_recording_ui()
            self._create_processing_ui()
            self._create_review_ui()

        # Store text for callbacks
        self._original_text = original
        self._improved_text = improved

        # Stop recording animations
        self._stop_timer()
        self._stop_pulse_animation()

        # Populate original text with inline diff
        self.original_text.config(state=tk.NORMAL)
        self.original_text.delete("1.0", tk.END)
        diff = self._compute_word_diff(original, improved)
        for tag, text in diff:
            if tag == "equal":
                self.original_text.insert(tk.END, text + " ")
            elif tag == "del":
                self.original_text.insert(tk.END, text + " ", "del")
            elif tag == "add":
                self.original_text.insert(tk.END, "[" + text + "] ", "add")
        self.original_text.config(state=tk.DISABLED)

        # Populate improved text
        self.improved_text.delete("1.0", tk.END)
        self.improved_text.insert("1.0", improved)

        self._position_window(self.REVIEW_WIDTH, self.REVIEW_HEIGHT)
        self.state = PanelState.REVIEW

        self.recording_frame.pack_forget()
        self.processing_frame.pack_forget()
        self.review_frame.pack(fill=tk.BOTH, expand=True)

        self.root.deiconify()
        self.root.lift()
        self._start_auto_dismiss()

    def hide(self):
        """Hide the panel with fade-out animation."""
        self._cancel_auto_dismiss()
        if self._current_alpha > 0.1:
            self._fade_out(callback=self._do_hide)
        else:
            self._do_hide()

    def destroy(self):
        """Destroy the panel window and clean up resources."""
        self._cancel_fade()
        self._cancel_transition()
        self._stop_timer()
        self._stop_pulse_animation()
        self._cancel_auto_dismiss()

        if self.root:
            self.root.destroy()
            self.root = None

        self.state = PanelState.HIDDEN

    def run(self):
        """Start the tkinter main loop."""
        if self.root:
            self.root.mainloop()


# =============================================================================
# Test / Demo Block
# =============================================================================

if __name__ == "__main__":
    import time
    import threading

    print("=" * 60)
    print("Glider Recording Panel - Demo")
    print("=" * 60)
    print()
    print("This demo will cycle through all panel states:")
    print("  1. RECORDING state (5 seconds)")
    print("  2. PROCESSING state (2 seconds)")
    print("  3. REVIEW state (Accept/Reject)")
    print("  4. HIDDEN state")
    print()
    print("Features:")
    print("  - Smooth fade in/out animations")
    print("  - Animated panel transitions")
    print("  - Rounded corners with translucent background")
    print("  - Horizontal layout with separators")
    print("  - Auto-dismiss in review state (6 seconds)")
    print()
    print("Press Ctrl+C in terminal to exit early")
    print("=" * 60)
    print()

    def on_accept(text):
        print(f"[Demo] ACCEPTED: {text[:50]}...")

    def on_reject(text):
        print(f"[Demo] REJECTED: {text[:50]}...")

    panel = PanelWindow(on_accept=on_accept, on_reject=on_reject)

    def demo_cycle():
        """Run through the demo states."""
        # State 1: Recording
        print("[Demo] Showing RECORDING state...")
        panel.show_recording(mode_name="Dictation")

        # Simulate audio levels
        for i in range(50):
            if panel.state != PanelState.RECORDING:
                break
            import math

            audio = 0.3 + 0.4 * (math.sin(i * 0.3) + 1) / 2
            panel.update_waveform(audio)
            time.sleep(0.1)

        if panel.state != PanelState.RECORDING:
            return

        time.sleep(1)

        # State 2: Processing
        print("[Demo] Showing PROCESSING state...")
        panel.show_processing()
        time.sleep(2)

        # State 3: Review
        print("[Demo] Showing REVIEW state...")
        print("[Demo] Panel will auto-dismiss in 6 seconds if not interacted with")
        panel.show_review(
            original="Um, so like, I was thinking that maybe we should, uh, consider the possibility of looking into this issue at some point in the near future.",
            improved="I recommend we prioritize investigating this issue within the next sprint.",
        )

        print("[Demo] Waiting for user action (Accept/Reject/Auto-dismiss)...")

    # Run demo in background thread
    demo_thread = threading.Thread(target=demo_cycle, daemon=True)
    demo_thread.start()

    # Start tkinter main loop
    try:
        panel.run()
    except KeyboardInterrupt:
        print("\n[Demo] Interrupted by user")
        panel.destroy()
