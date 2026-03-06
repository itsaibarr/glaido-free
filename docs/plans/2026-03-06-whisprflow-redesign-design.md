# WhisperFlow-Style UI Redesign

**Date:** 2026-03-06
**File:** `recording_panel.py`
**Status:** Approved

## Problem

The current recording panel has three major issues:

1. **Critical bug**: `_draw_rounded_rect()` clamps radius and checks `radius < 1` but has no drawing code for the normal case — the rounded rectangle is never drawn, so the pill shape does not exist.
2. **Color/style mismatch**: `BORDER_COLOR` uses CSS `rgba()` notation which tkinter ignores. Font stack includes `SF Pro Display` which is unavailable on Linux.
3. **Layout and animation quality**: Large buttons dominate the review panel; animations are basic linear fades; the waveform is underwhelming.

## Approach

Full visual rewrite of `recording_panel.py`, keeping the public API identical:
- `show_recording(mode_name)`, `show_processing()`, `show_review(original, improved)`
- `hide()`, `destroy()`, `update_waveform(level)`, `set_timer(seconds)`, `update_mode(name)`
- `on_accept`, `on_reject`, `on_stop`, `on_cancel` callbacks

## Color Palette

```
BG_COLOR        = "#0d0d0e"   # Near-black pill background
SURFACE_COLOR   = "#17171a"   # Inner surfaces
BORDER_COLOR    = "#2a2a2f"   # Subtle 1px border
FG_PRIMARY      = "#f5f5f7"   # Primary text
FG_SECONDARY    = "#86868b"   # Secondary / labels
ACCENT          = "#8b5cf6"   # Violet (WhisperFlow signature)
ACCENT_GLOW     = "#a78bfa"   # Lighter violet for waveform peaks
REC_DOT         = "#ef4444"   # Red recording indicator
ADD_COLOR       = "#34d399"   # Diff: added words (emerald)
DEL_COLOR       = "#f87171"   # Diff: removed words (strikethrough)
```

Fonts: `JetBrains Mono` / `SF Mono` / `Consolas` for timer and keyboard hints. `Inter` / `SF Pro Display` / `system-ui` for labels.

## Layouts

### Recording Pill (320x58, radius=29 — full capsule)

```
[ ● ]  [▁▃▅▇▅▃▁▃▅▃▁]  [ 00:12 ]  [ Transcribe ]
 red    purple waveform   mono      tiny violet pill
```

- Full capsule shape using smooth polygon (fix for the rounded rect bug)
- 20 waveform bars: 3px wide, 2px gap, rounded cap effect

### Processing Pill (same 320x58)

```
[ ◌ rotating arc ]  transcribing...         [ 00:12 ]
```

- 8-segment arc spinner replacing waveform, rotating at 90 deg/s

### Review Card (540x420, radius=20)

```
  Original
  Um so I was thinking we should ~~look into~~ [investigate] this soon
  (strikethrough red = removed, bold emerald = added)

  ──────────────────────────────

  Improved  ✦
  I recommend we investigate this soon.
  [editable]

  ──────────────────────────────

                     ↵ Accept  ·  ⎋ Dismiss
```

- Word-level diff using tkinter text tags: `del` (red + overstrike), `add` (emerald + bold)
- Keyboard hints rendered in monospace, right-aligned, small (10px)
- No large colored buttons

## Animations

| Animation | Duration | Easing |
|-----------|----------|--------|
| Fade in/out | 150ms, 10 steps | ease-out |
| Pill → Card geometry | 200ms, 12 steps | ease-out cubic |
| Recording dot pulse | 1200ms cycle | sin() |
| Waveform update | 30fps | direct |
| Processing spinner | continuous | linear 90deg/s |

**Waveform behavior:**
- Rest (no audio > 100ms): gentle breathing, bars 2–6px, `sin(time * 0.8)`
- Active: bars react to RMS, center bars taller, edge bars shorter, peak bars use `ACCENT_GLOW`

**Rounded rect fix:**
- Replace current broken implementation with smooth polygon:
  ```python
  points = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2,
            x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
  canvas.create_polygon(points, smooth=True, **kwargs)
  ```

## Word Diff Algorithm

Simple token-level diff using `difflib.SequenceMatcher`:
1. Tokenize both strings by whitespace
2. Compute opcodes: `equal`, `insert`, `delete`, `replace`
3. Render into the `original_text` widget using tag ranges:
   - `equal` → plain white
   - `delete` → red + `overstrike` font option
   - `insert` → shown inline as `[word]` in emerald bold
   - `replace` → old word red strikethrough + new word emerald bold adjacent

## Files Changed

- `recording_panel.py` — full visual rewrite (public API unchanged)
