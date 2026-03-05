# Glider free — Recording Panel & English Improvement System

## Overview

Glider is a keyboard-driven voice capture tool designed for **instant speech-to-text input**.  
The core workflow is:

1. User presses a **hotkey**.
2. Recording starts immediately.
3. User speaks.
4. User presses the **same hotkey again**.
5. Recording stops.
6. Audio is transcribed using **Grok / speech-to-text**.
7. Resulting text is automatically **pasted into the clipboard / active input field**.

The goal of **Glider free** is to significantly improve the **recording experience**, reduce **notification noise**, and introduce a new **English improvement mode**.

This document describes the **Recording Panel System**, **Mode Switching**, and **English Learning Feedback**.

---

# 1. Replace Notification-Based Feedback with a Recording Panel

## Problem

The current system relies on **system notifications** when:

- recording starts
- recording stops

This creates several issues:

- too many notifications
- disruptive workflow
- poor visibility of recording state
- no visual feedback of audio activity

Instead of notifications, Glider should display a **minimal interactive recording panel**.

---

# 2. Floating Recording Panel

Inspired by **WhisperFlow**, Glider should display a **floating recording interface** at the **bottom center of the screen** when recording starts.

The panel acts as a **visual indicator and controller for recording state**.

### Behavior

When user presses the **record hotkey**:

- recording starts
- a **floating panel animates into view**
- the panel displays **live audio waveform**
- panel remains visible while recording

When recording stops:

- the panel **expands into a larger review panel**
- transcription and analysis appear

---

# 3. Recording Panel (While Recording)

### Panel Position

- bottom center of screen
- floating above other windows
- small and non-intrusive

### Panel Elements

The panel contains:

**1. Recording Indicator**

- red dot or animated pulse
- clearly shows recording is active

**2. Live Audio Waves**

Audio waveform visualizer that reacts to microphone input.

Purpose:

- confirms microphone is working
- gives immediate feedback on speech loudness
- creates an intuitive recording feel

**3. Recording Timer**

Shows:
00:04
00:18
01:02


Helps user track speech length.

**4. Mode Indicator**

Shows current input mode:

MODE: Dictation


or


MODE: Prompt


---

# 4. Hotkey System

## Record Toggle

Primary hotkey:


(record hotkey)


Behavior:


Press → Start recording
Press again → Stop recording


---

## Mode Switching

Hotkey:


CTRL + SHIFT + M


This switches between **two modes**.

### Mode 1 — Dictation Mode

Default mode.

Behavior:

- speech is transcribed
- text is pasted directly into clipboard / input field

Example use:

- writing messages
- coding prompts
- quick text input

---

### Mode 2 — Prompt Mode

Prompt Mode transforms speech into **structured AI prompts**.

Example:

User says:

> create a python function that sorts a list

System outputs structured prompt like:


Write a Python function that sorts a list efficiently.
Include comments explaining the logic.


This mode is designed for **AI interactions and coding workflows**.

It was implemented but not working.
---

# 5. Recording Stop Behavior

When recording stops:

Instead of disappearing, the recording panel should **expand into a review panel**.

This transition should feel **smooth and animated**.

### Animation

Panel expands from:


small floating bar


to


medium floating window


Position remains bottom-center.

---

# 6. Review Panel

The expanded panel displays **three main sections**.

---

## 6.1 Original Transcription

The system shows the **raw speech transcription**.

Example:


Original:

i think the main problem with this app is that
it doesn't show any feedback while recording
so users feel unsure if it works


---

## 6.2 Improved English Version

Glider should send the transcription to an **LLM refinement step**.

Goal:

- improve grammar
- improve vocabulary
- keep original meaning

Example:


Improved Version:

I believe the main issue with this application is the lack of
feedback during recording. Because of this, users may feel
uncertain whether the system is functioning correctly.


---

## 6.3 Highlight Improvements

The system should highlight:

- corrected grammar
- improved vocabulary
- rewritten phrases

Example:


"i think" → "I believe"
"problem with this app" → "main issue with this application"


Purpose:

This transforms Glider into a **daily English speaking trainer**.

---

# 7. English Skill Development Feature

Glider should not only transcribe speech but also help improve English.

Each recording produces:

### 1. Raw Speech

User's original spoken text.

### 2. Improved Version

AI-corrected version with better:

- grammar
- structure
- vocabulary

### 3. Optional Suggestions

Examples:


Instead of: "very important"
Try: "crucial"

Instead of: "a lot of"
Try: "numerous"


This provides **passive language learning through everyday usage**.

---

# 8. Clipboard Behavior

Clipboard behavior depends on mode.

### Dictation Mode

Clipboard contains:


Improved English version


(or optionally original depending on settings)

---

### Prompt Mode

Clipboard contains:


AI structured prompt


---

# 9. UI States

The panel has **three states**.

---

## Idle

Panel hidden.

---

## Recording

Small floating panel with:

- waveform
- timer
- mode indicator

---

## Review

Expanded panel with:

- transcription
- improved English
- suggestions

---

# 10. Design Principles

The UI should follow these rules:

### Minimal

The panel must not block workflow.

### Keyboard-first

The system should work entirely with hotkeys.

### Immediate feedback

Users must instantly see:

- when recording starts
- whether microphone is active

### Learning-oriented

The system should gradually improve the user's English.

---

# 11. Target Use Cases

Glider is designed for:

- developers
- AI users
- prompt engineers
- language learners

Typical use:


Press hotkey
Speak idea
Stop recording
Receive improved text
Paste instantly


---

# 12. Summary

Glider 3 introduces:

- **floating recording panel**
- **live waveform visualization**
- **mode switching (Dictation / Prompt)**
- **expanded review interface**
- **AI-powered English improvement**
- **reduced notification clutter**

The system evolves from a simple **speech-to-text tool** into a **voice-first productivity and language improvement interface**.