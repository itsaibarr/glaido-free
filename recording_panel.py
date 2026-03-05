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

    # Panel dimensions (per design spec)
    RECORDING_WIDTH = 300
    RECORDING_HEIGHT = 48
    REVIEW_WIDTH = 580
    REVIEW_HEIGHT = 300
    BOTTOM_MARGIN = 50
    BORDER_RADIUS = 26  # Capsule shape (24-28px range)

    # Animation settings
    FADE_DURATION = 150  # ms for fade in/out
    FADE_STEPS = 10
    TRANSITION_DURATION = 150  # ms for size transitions
    TRANSITION_STEPS = 10

    # Auto-dismiss settings
    AUTO_DISMISS_DELAY = 6000  # 6 seconds (5-8 second range)

    # Colors (Dark theme with translucent background)
    BG_COLOR = "#141414"  # rgba(20,20,20) - translucent via wm_attributes
    FG_COLOR = "#ffffff"
    ACCENT_COLOR = "#ff4444"  # Red for recording indicator
    SECONDARY_BG = "#2d2d2d"
    BUTTON_ACCEPT = "#4caf50"
    BUTTON_REJECT = "#f44336"
    WAVE_COLOR = "#4a9eff"
    WAVE_COLOR_HIGH = "#ff6b6b"
    HIGHLIGHT_ADD = "#4caf50"  # Green for additions
    HIGHLIGHT_DEL = "#f44336"  # Red for deletions
    SUGGESTION_BG = "#3d3d3d"
    BORDER_COLOR = "#0f0f0f"  # Subtle border (will draw with alpha)
    TIMER_COLOR = "#b0b0b0"  # Slightly dimmed timer
    MODE_BG_COLOR = "#2a2a2a"  # Muted background for mode capsule
    TRANSPARENT_COLOR = "#010101"  # Special color for corner transparency on Linux

    # Font fallbacks
    FONT_PRIMARY = (
        "SF Pro Display",
        "Segoe UI",
        "Helvetica Neue",
        "Arial",
        "sans-serif",
    )
    FONT_MONO = ("SF Mono", "SFMono-Regular", "Consolas", "Monaco", "monospace")

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

        # Widget references
        self.recording_frame = None
        self.review_frame = None
        self.processing_frame = None
        self.timer_label = None
        self.mode_label = None
        self.mode_capsule = None
        self.indicator_canvas = None
        self.waveform_canvas = None
        self.original_text = None
        self.improved_text = None
        self.suggestions_text = None
        self.title_label = None
        self.content_container = None

    def _get_font(self, font_type="primary", size=12, weight="normal"):
        """Get font tuple with fallbacks."""
        if font_type == "mono":
            return self.FONT_MONO[:2] + (size, weight)
        else:
            return self.FONT_PRIMARY[:1] + (size, weight)

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
            # Draw subtle border first (slightly larger)
            self._draw_rounded_rect(
                0, 0, width, height, radius, fill=self.BORDER_COLOR, outline=""
            )

            # Draw main background (inset by 1px for border effect)
            self._draw_rounded_rect(
                1, 1, width - 1, height - 1, radius - 1, fill=self.BG_COLOR, outline=""
            )

        # Position the content container frame inside the rounded rectangle
        # Account for the border radius to keep content inside rounded corners
        inset = radius // 2
        self.content_container.place(
            x=inset, y=4, width=width - 2 * inset, height=height - 8
        )
        self._canvas.update_idletasks()

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Draw a rounded rectangle on the canvas using proper arc segments."""
        # Clamp radius to half the minimum dimension
        max_radius = min((x2 - x1) // 2, (y2 - y1) // 2)
        radius = min(radius, max_radius)

        if radius < 1:
            # Fall back to regular rectangle if radius is too small
            return self._canvas.create_rectangle(x1, y1, x2, y2, **kwargs)

        # Create arcs for corners and rectangles for sides
        # Using create_arc for corners and create_rectangle for the center

        # Top-left corner arc (90-180 degrees)
        arc_tl = self._canvas.create_arc(
            x1,
            y1,
            x1 + 2 * radius,
            y1 + 2 * radius,
            start=90,
            extent=90,
            style=tk.PIESLICE,
            **kwargs,
        )

        # Top-right corner arc (0-90 degrees)
        arc_tr = self._canvas.create_arc(
            x2 - 2 * radius,
            y1,
            x2,
            y1 + 2 * radius,
            start=0,
            extent=90,
            style=tk.PIESLICE,
            **kwargs,
        )

        # Bottom-right corner arc (270-360 degrees)
        arc_br = self._canvas.create_arc(
            x2 - 2 * radius,
            y2 - 2 * radius,
            x2,
            y2,
            start=270,
            extent=90,
            style=tk.PIESLICE,
            **kwargs,
        )

        # Bottom-left corner arc (180-270 degrees)
        arc_bl = self._canvas.create_arc(
            x1,
            y2 - 2 * radius,
            x1 + 2 * radius,
            y2,
            start=180,
            extent=90,
            style=tk.PIESLICE,
            **kwargs,
        )

        # Center rectangle
        rect_center = self._canvas.create_rectangle(
            x1 + radius, y1, x2 - radius, y2, **kwargs
        )

        # Side rectangles to fill gaps
        rect_left = self._canvas.create_rectangle(
            x1, y1 + radius, x1 + radius, y2 - radius, **kwargs
        )

        rect_right = self._canvas.create_rectangle(
            x2 - radius, y1 + radius, x2, y2 - radius, **kwargs
        )

        # Return the center rectangle ID as the main reference
        return rect_center

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
        """Create the recording panel UI widgets with horizontal layout."""
        widget_bg = self._get_widget_bg()
        self.recording_frame = tk.Frame(self.content_container, bg=widget_bg)

        # Layout: [Dot] [Waveform] | [Timer] | [Mode] horizontal with separators

        # Left section: Recording indicator
        left_frame = tk.Frame(self.recording_frame, bg=widget_bg)
        left_frame.pack(side=tk.LEFT, padx=(12, 8))

        self.indicator_canvas = tk.Canvas(
            left_frame,
            width=16,
            height=16,
            bg=widget_bg,
            highlightthickness=0,
        )
        self.indicator_canvas.pack()

        # Create pulsing red circle (8px diameter)
        self.indicator_circle = self.indicator_canvas.create_oval(
            4, 4, 12, 12, fill=self.ACCENT_COLOR, outline=""
        )

        # Waveform section
        wave_frame = tk.Frame(self.recording_frame, bg=widget_bg)
        wave_frame.pack(side=tk.LEFT, padx=(0, 8))

        self.waveform_canvas = tk.Canvas(
            wave_frame,
            width=80,
            height=32,
            bg=widget_bg,
            highlightthickness=0,
        )
        self.waveform_canvas.pack()

        # Draw initial waveform placeholder
        self._draw_waveform(0.0)

        # Separator 1
        sep1 = self._create_separator(self.recording_frame, height=20)
        sep1.pack(side=tk.LEFT, padx=4)

        # Timer section (monospace, slightly dimmed)
        timer_frame = tk.Frame(self.recording_frame, bg=widget_bg)
        timer_frame.pack(side=tk.LEFT, padx=8)

        self.timer_label = tk.Label(
            timer_frame,
            text="00:00",
            font=("SF Mono", 11, "normal"),
            bg=widget_bg,
            fg=self.TIMER_COLOR,
        )
        self.timer_label.pack()

        # Separator 2
        sep2 = self._create_separator(self.recording_frame, height=20)
        sep2.pack(side=tk.LEFT, padx=4)

        # Mode section (small capsule label)
        mode_frame = tk.Frame(self.recording_frame, bg=widget_bg)
        mode_frame.pack(side=tk.LEFT, padx=(4, 12))

        # Mode capsule with muted background (keep distinct color even on Linux)
        self.mode_capsule = tk.Frame(
            mode_frame,
            bg=self.MODE_BG_COLOR,
            padx=8,
            pady=2,
        )
        self.mode_capsule.pack()

        self.mode_label = tk.Label(
            self.mode_capsule,
            text="Dictation",
            font=("SF Pro Display", 9),
            bg=self.MODE_BG_COLOR,
            fg="#aaaaaa",
        )
        self.mode_label.pack()

    def _create_processing_ui(self):
        """Create the processing panel UI widgets."""
        widget_bg = self._get_widget_bg()
        self.processing_frame = tk.Frame(self.content_container, bg=widget_bg)

        # Center content
        center_container = tk.Frame(self.processing_frame, bg=widget_bg)
        center_container.pack(expand=True)

        # Processing spinner (animated dots)
        self.processing_label = tk.Label(
            center_container,
            text="Processing...",
            font=("SF Pro Display", 14, "bold"),
            bg=widget_bg,
            fg=self.FG_COLOR,
        )
        self.processing_label.pack(pady=(0, 8))

        self.processing_subtitle = tk.Label(
            center_container,
            text="Transcribing and improving...",
            font=("SF Pro Text", 10),
            bg=widget_bg,
            fg="#888888",
        )
        self.processing_subtitle.pack()

        # Animate the dots
        self._animate_processing()

    def _animate_processing(self):
        """Animate the processing text."""
        if self.state != PanelState.PROCESSING or not self.processing_label:
            return

        dots = ["", ".", "..", "..."]
        current = self.processing_label.cget("text")
        base = "Processing"
        next_dots = dots[(dots.index(current[len(base) :]) + 1) % len(dots)]
        self.processing_label.config(text=base + next_dots)

        if self.root:
            self.root.after(500, self._animate_processing)

    def _create_review_ui(self):
        """Create the review panel UI widgets with diff highlighting."""
        widget_bg = self._get_widget_bg()
        self.review_frame = tk.Frame(self.content_container, bg=widget_bg)

        # Bind mouse events for auto-dismiss
        self.review_frame.bind("<Enter>", self._on_review_enter)
        self.review_frame.bind("<Leave>", self._on_review_leave)

        # Title
        self.title_label = tk.Label(
            self.review_frame,
            text="Review Improvements",
            font=("SF Pro Display", 14, "bold"),
            bg=widget_bg,
            fg=self.FG_COLOR,
        )
        self.title_label.pack(pady=(12, 8))
        self.title_label.bind("<Enter>", self._on_review_enter)
        self.title_label.bind("<Leave>", self._on_review_leave)

        # Instructions with better visual styling
        instructions_frame = tk.Frame(self.review_frame, bg=widget_bg)
        instructions_frame.pack(pady=(0, 8))
        instructions_frame.bind("<Enter>", self._on_review_enter)
        instructions_frame.bind("<Leave>", self._on_review_leave)

        instructions = tk.Label(
            instructions_frame,
            text="Press Enter to Accept  •  Press Escape to Reject",
            font=("SF Pro Text", 9),
            bg=widget_bg,
            fg="#666666",
        )
        instructions.pack()
        instructions.bind("<Enter>", self._on_review_enter)
        instructions.bind("<Leave>", self._on_review_leave)

        # Content frame for text areas
        content_frame = tk.Frame(self.review_frame, bg=widget_bg)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=16)
        content_frame.bind("<Enter>", self._on_review_enter)
        content_frame.bind("<Leave>", self._on_review_leave)

        # Original text section
        original_frame = tk.Frame(content_frame, bg=self.SECONDARY_BG, padx=8, pady=8)
        original_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        original_frame.bind("<Enter>", self._on_review_enter)
        original_frame.bind("<Leave>", self._on_review_leave)

        tk.Label(
            original_frame,
            text="Original",
            font=("SF Pro Text", 10, "bold"),
            bg=self.SECONDARY_BG,
            fg="#888888",
        ).pack(anchor=tk.W, pady=(0, 4))

        self.original_text = tk.Text(
            original_frame,
            height=3,
            wrap=tk.WORD,
            font=("SF Pro Text", 11),
            bg=self.SECONDARY_BG,
            fg=self.FG_COLOR,
            relief=tk.FLAT,
            highlightthickness=0,
            padx=4,
            pady=4,
        )
        self.original_text.pack(fill=tk.BOTH, expand=True)
        self.original_text.config(state=tk.DISABLED)
        self.original_text.bind("<Enter>", self._on_review_enter)
        self.original_text.bind("<Leave>", self._on_review_leave)

        # Improved text section with diff highlighting
        improved_frame = tk.Frame(content_frame, bg=self.SECONDARY_BG, padx=8, pady=8)
        improved_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 4))
        improved_frame.bind("<Enter>", self._on_review_enter)
        improved_frame.bind("<Leave>", self._on_review_leave)

        tk.Label(
            improved_frame,
            text="Improved",
            font=("SF Pro Text", 10, "bold"),
            bg=self.SECONDARY_BG,
            fg="#4caf50",
        ).pack(anchor=tk.W, pady=(0, 4))

        self.improved_text = tk.Text(
            improved_frame,
            height=3,
            wrap=tk.WORD,
            font=("SF Pro Text", 11),
            bg=self.SECONDARY_BG,
            fg=self.FG_COLOR,
            relief=tk.FLAT,
            highlightthickness=0,
            padx=4,
            pady=4,
        )
        self.improved_text.pack(fill=tk.BOTH, expand=True)
        self.improved_text.bind("<Enter>", self._on_review_enter)
        self.improved_text.bind("<Leave>", self._on_review_leave)

        # Configure tags for diff highlighting with better contrast
        self.improved_text.tag_configure(
            "added",
            background="#2d5a3d",
            foreground="#90ee90",
            font=("SF Pro Text", 11, "bold"),
        )
        self.improved_text.tag_configure(
            "removed",
            background="#5a2d2d",
            foreground="#ff9999",
            font=("SF Pro Text", 11),
        )

        self.improved_text.config(state=tk.DISABLED)

        # Suggestions section
        suggestions_frame = tk.Frame(
            content_frame, bg=self.SUGGESTION_BG, padx=8, pady=6
        )
        suggestions_frame.pack(fill=tk.X, pady=(4, 8))
        suggestions_frame.bind("<Enter>", self._on_review_enter)
        suggestions_frame.bind("<Leave>", self._on_review_leave)

        tk.Label(
            suggestions_frame,
            text="Key Improvements",
            font=("SF Pro Text", 9, "bold"),
            bg=self.SUGGESTION_BG,
            fg="#aaaaaa",
        ).pack(anchor=tk.W, pady=(0, 4))

        self.suggestions_text = tk.Text(
            suggestions_frame,
            height=2,
            wrap=tk.WORD,
            font=("SF Pro Text", 9),
            bg=self.SUGGESTION_BG,
            fg="#cccccc",
            relief=tk.FLAT,
            highlightthickness=0,
            padx=4,
            pady=3,
        )
        self.suggestions_text.pack(fill=tk.X)
        self.suggestions_text.config(state=tk.DISABLED)
        self.suggestions_text.bind("<Enter>", self._on_review_enter)
        self.suggestions_text.bind("<Leave>", self._on_review_leave)

        # Buttons frame with consistent spacing
        button_frame = tk.Frame(self.review_frame, bg=self.BG_COLOR)
        button_frame.pack(pady=(0, 12), padx=16, fill=tk.X)
        button_frame.bind("<Enter>", self._on_review_enter)
        button_frame.bind("<Leave>", self._on_review_leave)

        # Reject button with hover effect
        self.reject_btn = tk.Button(
            button_frame,
            text="✕ Reject (Esc)",
            font=("SF Pro Text", 11),
            bg=self.BUTTON_REJECT,
            fg=self.FG_COLOR,
            activebackground="#d32f2f",
            activeforeground=self.FG_COLOR,
            relief=tk.FLAT,
            padx=20,
            pady=6,
            cursor="hand2",
            command=self._on_reject,
        )
        self.reject_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.reject_btn.bind("<Enter>", self._on_review_enter)
        self.reject_btn.bind("<Leave>", self._on_review_leave)

        # Accept button with hover effect
        self.accept_btn = tk.Button(
            button_frame,
            text="✓ Accept (Enter)",
            font=("SF Pro Text", 11),
            bg=self.BUTTON_ACCEPT,
            fg=self.FG_COLOR,
            activebackground="#388e3c",
            activeforeground=self.FG_COLOR,
            relief=tk.FLAT,
            padx=20,
            pady=6,
            cursor="hand2",
            command=self._on_accept,
        )
        self.accept_btn.pack(side=tk.RIGHT)
        self.accept_btn.bind("<Enter>", self._on_review_enter)
        self.accept_btn.bind("<Leave>", self._on_review_leave)

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
        """Draw a waveform visualization on the canvas."""
        self.waveform_canvas.delete("all")

        width = 80
        height = 32
        center_y = height // 2

        # Draw waveform bars
        num_bars = 10
        bar_width = 4
        gap = 3

        for i in range(num_bars):
            x = i * (bar_width + gap) + 3

            # Create wave effect based on position and audio level
            wave = math.sin((i + self.timer_seconds * 5) * 0.5) * 0.5 + 0.5
            bar_height = (3 + wave * 12) * (0.3 + audio_level * 0.7)

            # Color gradient based on audio level
            if audio_level > 0.7:
                color = self.WAVE_COLOR_HIGH
            else:
                color = self.WAVE_COLOR

            self.waveform_canvas.create_rectangle(
                x,
                center_y - bar_height / 2,
                x + bar_width,
                center_y + bar_height / 2,
                fill=color,
                outline="",
            )

    def _start_pulse_animation(self):
        """Start the recording indicator pulse animation."""
        if self.state != PanelState.RECORDING:
            return

        # Calculate pulse opacity
        self.pulse_state += 0.15
        pulse = (math.sin(self.pulse_state) + 1) / 2  # 0.0 to 1.0

        # Adjust color brightness based on pulse
        r = int(255 * (0.6 + 0.4 * pulse))
        color = f"#{r:02x}4444"

        if self.indicator_canvas:
            self.indicator_canvas.itemconfig(self.indicator_circle, fill=color)

        self.pulse_job = self.root.after(50, self._start_pulse_animation)

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
        Update the waveform visualization.

        Args:
            audio_level: Float between 0.0 and 1.0 representing audio amplitude
        """
        if self.state != PanelState.RECORDING or self.waveform_canvas is None:
            return

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
        """
        Expand to review panel with original and improved text comparison.
        Includes smooth transition animation and auto-dismiss.

        Args:
            original: The original transcribed text
            improved: The AI-improved text
        """
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

        # Hide all frames first
        self.recording_frame.pack_forget()
        self.processing_frame.pack_forget()
        self.review_frame.pack_forget()

        # Show review frame
        self.state = PanelState.REVIEW
        self.review_frame.pack(fill=tk.BOTH, expand=True)

        # Update original text
        if self.original_text:
            self.original_text.config(state=tk.NORMAL)
            self.original_text.delete("1.0", tk.END)
            self.original_text.insert("1.0", original)
            self.original_text.config(state=tk.DISABLED)

        # Update improved text with diff highlighting
        if self.improved_text:
            diff_result = self._compute_diff(original, improved)
            self._insert_highlighted_text(self.improved_text, diff_result)

        # Update suggestions
        if self.suggestions_text:
            suggestions = self._extract_suggestions(original, improved)
            self.suggestions_text.config(state=tk.NORMAL)
            self.suggestions_text.delete("1.0", tk.END)
            if suggestions:
                self.suggestions_text.insert("1.0", "  •  ".join(suggestions))
            else:
                self.suggestions_text.insert(
                    "1.0", "Grammar and style improvements applied"
                )
            self.suggestions_text.config(state=tk.DISABLED)

        # Position and show window with smooth animation
        if self._current_geometry:
            # Animate from current position
            current = self._parse_geometry(self._current_geometry)
            target = {
                "width": self.REVIEW_WIDTH,
                "height": self.REVIEW_HEIGHT,
                "x": self._get_screen_center_x(self.REVIEW_WIDTH),
                "y": self._get_screen_bottom_y(self.REVIEW_HEIGHT),
            }
            self.root.deiconify()
            self.root.lift()
            self._animate_transition(current, target)
        else:
            self._position_window(self.REVIEW_WIDTH, self.REVIEW_HEIGHT)
            self.root.deiconify()
            self.root.lift()

        # Start auto-dismiss timer
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
