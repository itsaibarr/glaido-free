1. Context

Founder:
Aibar — full-stack developer building productivity tools and AI-based utilities.

Project:
Glaido Free — a hotkey-based voice transcription app.

Current Behavior:

Hold hotkey (ctrl+shift+space) → record voice

Release hotkey (ctrl+shift+space) → transcribe speech

Automatically paste text into active app

Primary use case: fast voice-to-text anywhere in OS.

2. Current Problems
   Problem 1 — Terminal Paste Issue

Text cannot be instantly pasted into Linux terminals.
Clipboard paste works in normal apps but fails in terminal.
User must manually paste elsewhere and re-copy.

Problem 2 — New Feature (Dual Mode)

Add second mode:

Mode A — Transcribe Mode
Speech → raw transcription → output

Mode B — Prompt Mode
Speech → optimized short AI prompt → output
Output should be compressed, structured, and AI-ready — not raw speech.

3. Required Architecture

Implement modular pipeline:

Hotkey
→ Audio Capture
→ Speech-to-Text
→ Processing Layer (Mode Switch)
→ Output Layer

4. Required Solutions
   Terminal Fix

Do NOT simulate paste.
Instead:
Simulate real keyboard typing (xdotool / ydotool / input injection library).
Terminal must detect it as real user typing.

Dual Mode Processing

Add internal state:
mode = "transcribe" | "prompt"

If mode == transcribe:
Output raw STT text.

If mode == prompt:
Send STT text to LLM with fixed system instruction:

Remove filler words

Compress intent

Return short, structured AI prompt

No explanations

Replace output with optimized prompt.

5. Design Constraints

Low latency

Modular processing layer (future expansion ready)

OS-level compatibility

No heavy UI complexity

Clean separation: STT ≠ Processing ≠ Output

6. Goal

Transform Glider from simple voice-to-text tool
into lightweight AI productivity assistant
with terminal compatibility and prompt-engineering mode.
