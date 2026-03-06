
# WhisperFlow UI Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite `recording_panel.py` to look and feel like WhisperFlow — ultra-compact dark pill, violet waveform, inline word-diff review, keyboard-first actions.

**Architecture:** Single-file rewrite of all visual/animation constants and UI-building methods in `recording_panel.py`. Public API (show_recording, show_processing, show_review, hide, destroy, update_waveform, set_timer, update_mode, all callbacks) stays identical so `glaido.py` needs no changes.

**Tech Stack:** Python 3, tkinter (stdlib), difflib (stdlib)

**Design doc:** `docs/plans/2026-03-06-whisprflow-redesign-design.md`

---

### Task 1: Fix `_draw_rounded_rect` bug

The method currently has NO drawing code for the normal case (radius >= 1). It only handles the degenerate `radius < 1` fallback. Everything else silently returns `None`.

**Files:**
- Modify: `recording_panel.py` — method `_draw_rounded_rect` (~line 263)
- Test: `test_panel.py` (existing file, add one test)

**Step 1: Read the existing test file to understand test style**

Read `test_panel.py` to understand existing test patterns.

**Step 2: Write a failing test**

Add to `test_panel.py`:

```python
def test_draw_rounded_rect_returns_item_id():
    """_draw_rounded_rect must return a canvas item id (int), not None."""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=200, height=100)
    from recording_panel import PanelWindow
    panel = PanelWindow()
    panel._canvas = canvas
    result = panel._draw_rounded_rect(10, 10, 190, 90, 20, fill="#ff0000")
    assert result is not None, "Expected a canvas item id, got None"
    assert isinstance(result, int), f"Expected int item id, got {type(result)}"
    root.destroy()
```

**Step 3: Run test to verify it fails**

```bash
cd /home/itsaibarr/projects/glaido-free
python -m pytest test_panel.py::test_draw_rounded_rect_returns_item_id -v
```

Expected: FAIL — `AssertionError: Expected a canvas item id, got None`

**Step 4: Fix `_draw_rounded_rect` in `recording_panel.py`**

Replace the entire method body with:

```python
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
```

**Step 5: Run test to verify it passes**

```bash
python -m pytest test_panel.py::test_draw_rounded_rect_returns_item_id -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add recording_panel.py test_panel.py
git commit -m "fix: draw rounded rect using smooth polygon — was returning None"
```

---

### Task 2: Apply WhisperFlow color palette and constants

Replace all color/dimension constants at the top of `PanelWindow` with the new WhisperFlow palette.

**Files:**
- Modify: `recording_panel.py` — class-level constants (~lines 33–78)

**Step 1: Replace constants block**

Find the block between `# ── Dimensions` and `# ── Typography` comments and replace with:

```python
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

# ── Typography ──
FONT_PRIMARY = ("Inter", "SF Pro Display", "Helvetica Neue", "Arial", "sans-serif")
FONT_MONO = ("JetBrains Mono", "SF Mono", "Consolas", "Monaco", "monospace")
```

Note: Remove `BORDER_COLOR = "rgba(255,255,255,0.08)"` — the CSS rgba value was silently ignored by tkinter. Use `BORDER_COLOR_HEX` instead.

**Step 2: Fix all references to old constants**

Search for any usage of the old names that changed:
- `BORDER_COLOR` → `BORDER_COLOR_HEX` (used in `_on_resize`)
- `BUTTON_ACCEPT`, `BUTTON_REJECT` → no longer needed (buttons removed in Task 5)
- `HIGHLIGHT_ADD`, `HIGHLIGHT_DEL`, `SUGGESTION_BG` → remove (replaced by `ADD_COLOR`, `DEL_COLOR`)

**Step 3: Run the demo to verify no crashes**

```bash
python recording_panel.py
```

Expected: Panel appears (may look unstyled yet), no Python errors, auto-cycles through states.

**Step 4: Commit**

```bash
git add recording_panel.py
git commit -m "style: apply WhisperFlow color palette and fix rgba border color"
```

---

### Task 3: Redesign the recording pill layout

Replace `_create_recording_ui` with a tight single-row capsule layout.

**Files:**
- Modify: `recording_panel.py` — method `_create_recording_ui` (~line 423)

**Step 1: Replace `_create_recording_ui` entirely**

```python
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
```

**Step 2: Run demo and visually verify pill layout**

```bash
python recording_panel.py
```

Expected: Compact single-row pill with dot, waveform, timer, mode label.

**Step 3: Commit**

```bash
git add recording_panel.py
git commit -m "style: redesign recording pill to WhisperFlow compact layout"
```

---

### Task 4: Redesign waveform and pulse animation

Replace `_draw_waveform` and `_start_pulse_animation` with the new 30fps reactive waveform.

**Files:**
- Modify: `recording_panel.py` — methods `_draw_waveform`, `_start_pulse_animation`

**Step 1: Replace `_draw_waveform`**

```python
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

        # Rounded cap: draw slightly rounded rectangle by overlapping rect + ovals
        y1 = center_y - h / 2
        y2 = center_y + h / 2
        self.waveform_canvas.create_rectangle(
            x, y1, x + bar_width, y2,
            fill=color, outline="",
        )
```

**Step 2: Replace `_start_pulse_animation`**

```python
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
```

**Step 3: Run demo and verify waveform**

```bash
python recording_panel.py
```

Expected: Violet breathing bars at rest, reactive bars when audio level is non-zero.

**Step 4: Commit**

```bash
git add recording_panel.py
git commit -m "style: WhisperFlow violet waveform with breathing animation at 30fps"
```

---

### Task 5: Redesign processing state with arc spinner

Replace `_create_processing_ui` and `_animate_processing` with a canvas-based arc spinner.

**Files:**
- Modify: `recording_panel.py` — methods `_create_processing_ui`, `_animate_processing`

**Step 1: Replace `_create_processing_ui`**

```python
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
```

**Step 2: Replace `_animate_processing`**

```python
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
```

**Step 3: Run demo and verify**

```bash
python recording_panel.py
```

Expected: Processing pill shows spinning violet arc + "transcribing..." dots.

**Step 4: Commit**

```bash
git add recording_panel.py
git commit -m "style: replace processing dots with arc spinner for WhisperFlow feel"
```

---

### Task 6: Add word-level diff algorithm

Add `_compute_word_diff` as a new method using `difflib`. This powers the review panel diff display.

**Files:**
- Modify: `recording_panel.py` — add method `_compute_word_diff`
- Test: `test_panel.py`

**Step 1: Write failing tests for the diff algorithm**

Add to `test_panel.py`:

```python
def test_compute_word_diff_equal():
    from recording_panel import PanelWindow
    panel = PanelWindow()
    result = panel._compute_word_diff("hello world", "hello world")
    # All tokens should be 'equal'
    assert all(tag == "equal" for tag, _ in result)

def test_compute_word_diff_replace():
    from recording_panel import PanelWindow
    panel = PanelWindow()
    result = panel._compute_word_diff("look into this", "investigate this")
    tags = [tag for tag, _ in result]
    assert "del" in tags
    assert "add" in tags

def test_compute_word_diff_returns_list_of_tuples():
    from recording_panel import PanelWindow
    panel = PanelWindow()
    result = panel._compute_word_diff("foo bar", "foo baz")
    assert isinstance(result, list)
    assert all(isinstance(t, tuple) and len(t) == 2 for t in result)
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest test_panel.py::test_compute_word_diff_equal test_panel.py::test_compute_word_diff_replace test_panel.py::test_compute_word_diff_returns_list_of_tuples -v
```

Expected: AttributeError — `_compute_word_diff` does not exist yet.

**Step 3: Implement `_compute_word_diff`**

Add this method to `PanelWindow` (after `_create_review_ui` is a good spot):

```python
def _compute_word_diff(self, original: str, improved: str) -> list:
    """
    Compute word-level diff between original and improved text.

    Returns list of (tag, text) tuples where tag is:
      'equal' — unchanged word(s)
      'del'   — word(s) in original but not improved (show strikethrough)
      'add'   — word(s) in improved but not original (show bold emerald)
    """
    import difflib
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
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest test_panel.py::test_compute_word_diff_equal test_panel.py::test_compute_word_diff_replace test_panel.py::test_compute_word_diff_returns_list_of_tuples -v
```

Expected: All 3 PASS.

**Step 5: Commit**

```bash
git add recording_panel.py test_panel.py
git commit -m "feat: add word-level diff algorithm for review panel (difflib)"
```

---

### Task 7: Redesign review panel with inline diff and keyboard hints

Replace `_create_review_ui` with the WhisperFlow-style card: diff view + keyboard-first actions.

**Files:**
- Modify: `recording_panel.py` — methods `_create_review_ui`, `show_review`

**Step 1: Replace `_create_review_ui`**

```python
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
```

**Step 2: Update `show_review` to populate the diff**

Find `show_review` and replace the original_text population block with:

```python
def show_review(self, original: str, improved: str):
    """Show the review panel with inline word diff."""
    self._original_text_str = original
    self._improved_text_str = improved

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

    self._resize_window(self.REVIEW_WIDTH, self.REVIEW_HEIGHT)
    self.state = PanelState.REVIEW

    self.recording_frame.pack_forget()
    self.processing_frame.pack_forget()
    self.review_frame.pack(fill=tk.BOTH, expand=True)

    self.root.deiconify()
    self.root.lift()
    self._start_auto_dismiss()
```

**Step 3: Remove old button references**

Delete `self.reject_btn` and `self.accept_btn` attribute assignments — they no longer exist. If `_create_review_ui` previously assigned them, remove those lines. The accept/reject logic is still handled by `_on_accept` / `_on_reject` via keyboard bindings.

**Step 4: Run demo and verify review panel visually**

```bash
python recording_panel.py
```

Expected: Review card shows diff in original section (red strikethrough = removed, green bold = added), improved text is editable, bottom shows `↵ Accept  ·  ⎋ Dismiss` right-aligned.

**Step 5: Commit**

```bash
git add recording_panel.py
git commit -m "feat: redesign review panel with inline word diff and keyboard hints"
```

---

### Task 8: Final polish — window background and border

Update `_on_resize` to use the new `BORDER_COLOR_HEX` constant and draw a proper 1px border.

**Files:**
- Modify: `recording_panel.py` — method `_on_resize` (~line 215)

**Step 1: Update the border drawing in `_on_resize`**

Replace the `else` branch that draws border + main background with:

```python
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
```

**Step 2: Set canvas background to match `BG_COLOR`**

In `_create_rounded_container`, ensure the canvas bg matches:

```python
self._canvas = tk.Canvas(
    self.root,
    bg=self.BG_COLOR,   # was previously BG_COLOR already — verify this
    highlightthickness=0,
    bd=0,
)
```

**Step 3: Run full demo cycle**

```bash
python recording_panel.py
```

Expected: Pill has clean dark background with subtle 1px border. Rounded corners are visible. All 3 states look correct.

**Step 4: Run all tests**

```bash
python -m pytest test_panel.py -v
```

Expected: All tests pass.

**Step 5: Commit**

```bash
git add recording_panel.py
git commit -m "style: fix border drawing in _on_resize to use WhisperFlow dark border"
```

---

### Task 9: Run full test suite and visual verification

**Step 1: Run all tests**

```bash
python -m pytest test_panel.py -v
```

Expected: All tests pass.

**Step 2: Run visual demo**

```bash
python recording_panel.py
```

Verify each state manually:
- [ ] Recording pill: compact, violet waveform breathing, red dot pulsing, timer ticking
- [ ] Processing: arc spinner rotating, "transcribing..." dots cycling
- [ ] Review: diff shown in original, improved editable, keyboard hints visible

**Step 3: Run via main app (smoke test)**

```bash
python glaido.py --test-panel
```

Expected: Panel cycles through states without errors. No API breakage.

**Step 4: Final commit if any fixes were needed**

```bash
git add recording_panel.py test_panel.py
git commit -m "test: verify WhisperFlow redesign passes all tests and visual checks"
```
