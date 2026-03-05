# Glider 3 — Recording Panel UI Design (WhisperFlow-Inspired)

## Overview

The Glider recording panel replaces system notifications with a **minimal floating interface** that provides clear feedback during voice capture.

The panel is inspired by **WhisperFlow's recording bar**, emphasizing:

- minimal UI
- fast visual feedback
- unobtrusive overlay
- keyboard-first interaction

The panel appears only during recording and expands after recording ends to show transcription and English improvements.

---

# Design Goals

1. **Non-intrusive**  
   The interface must not interrupt the user's workflow (coding, writing, browsing).

2. **Instant feedback**  
   The user should immediately see that recording is active.

3. **Minimal visual noise**  
   The panel should contain only essential information.

4. **Smooth transitions**  
   UI states must transition with subtle animations.

5. **Developer-friendly aesthetics**  
   The design language should resemble modern developer tools (Raycast, Linear, WhisperFlow).

---

# Panel Position

The recording panel appears as a floating element.

**Location**


Bottom-center of the screen


**Spacing**


40–60px above the bottom edge


**Behavior**

- Always visible above other windows
- Does not steal focus from the active application
- Appears only during recording

---

# Panel States

The interface has three states.


Idle
Recording
Review


### Idle

Panel is hidden.

### Recording

Small floating recording bar appears.

### Review

Panel expands to display transcription and language feedback.

---

# Recording Panel Layout

When recording starts, a compact horizontal bar appears.

Example layout:


● waveform animation | 00:12 | Dictation


Structure:


[Recording Dot] [Audio Waveform] | [Timer] | [Mode Indicator]


---

# Panel Dimensions

Approximate dimensions:


Height: 44–52px
Width: 260–340px
Border radius: 24–28px


Shape:


Rounded capsule


---

# Panel Appearance

## Background


rgba(20, 20, 20, 0.85)


Properties:

- dark translucent background
- subtle blur (glass effect)
- readable over any application

Optional effect:


backdrop-blur


---

## Border


1px rgba(255,255,255,0.06)


Provides subtle separation from the background.

---

## Shadow


0px 6px 18px rgba(0,0,0,0.25)


Creates floating effect.

---

# UI Components

## 1. Recording Indicator

Small animated dot on the left.

Purpose:

- indicates microphone is active
- confirms recording state

Example:


●


Properties:


Color: red
Size: ~8px


Animation:


Pulse every ~1 second


Behavior:

- appears when recording starts
- disappears when recording ends

---

## 2. Live Audio Waveform

Main visual element.

This waveform reacts to microphone input in real time.

Purpose:

- confirms microphone activity
- shows speech intensity
- provides visual engagement

Properties:


Horizontal animation
Smooth motion
Low amplitude height
Consistent rhythm


Possible waveform style:


▁▂▃▂▁ ▂▄▅▄▂ ▃▅▆▅▃


Implementation options:

- animated bars
- curved waveform
- amplitude visualization

Recommended animation speed:


30–60 FPS


Wave behavior:

| Audio Input | Wave Behavior |
|-------------|---------------|
| Silence | small movements |
| Speaking | larger peaks |
| Loud speech | higher amplitude |

---

## 3. Recording Timer

Displays how long the recording has been active.

Format:


MM:SS


Examples:


00:04
00:18
01:02


Typography recommendations:


Font: monospace or semi-monospace
Weight: medium
Color: slightly dimmed


Purpose:

- helps users manage recording length
- provides temporal context

---

## 4. Mode Indicator

Displays the active recording mode.

Possible values:


Dictation
Prompt


Example:


| Dictation


or


| Prompt


Recommended style:


Small rounded capsule label
Muted background
Compact padding


Example visual:


[Prompt]


---

# Animations

## Panel Entrance

When recording begins:

Animation:


Slide up + fade in


Motion:


translateY(20px → 0px)
opacity(0 → 1)


Duration:


150–200 ms


---

## Wave Animation

The waveform animates continuously during recording.

Behavior:

- reacts to microphone amplitude
- updates smoothly
- never fully stops while recording

---

## Recording Stop Transition

When recording stops:

1. waveform animation stops
2. short pause (~200ms)
3. panel expands into review panel

Animation properties:


Width expansion
Height expansion


Duration:


200–250 ms


---

# Review Panel

After recording ends, the panel expands to display speech feedback.

Approximate dimensions:


Width: 520–640px
Height: 260–360px


Position remains:


Bottom center


---

# Review Panel Layout

Vertical layout:


Original Speech
Improved Version
Vocabulary Improvements


---

## Section 1 — Original Speech

Displays the raw transcription from the speech-to-text engine.

Example:


Original

i think the system needs better visual feedback
because users cannot see if recording works


Style:


Smaller text
Muted color


---

## Section 2 — Improved Version

Displays the AI-improved version of the user's speech.

Example:


Improved

I believe the system requires clearer visual feedback,
because users cannot easily determine whether
recording is active.


Style:


Larger text
Higher contrast
Paragraph formatting


---

## Section 3 — Vocabulary Improvements

Shows suggested vocabulary upgrades.

Example:


Vocabulary Improvements

explain everything in detail → elaborate
make something easier → simplify
very important → crucial


Display format:


phrase → improved word


Purpose:

- help users learn concise vocabulary
- build language awareness

---

# Interaction Behavior

The panel should remain mostly passive.

Primary control remains **keyboard hotkeys**.

Optional interactions:


Copy improved text
Open vocabulary list
Dismiss panel


Mouse interaction should be minimal.

---

# Visibility Rules

Panel visibility logic:


Idle → hidden
Recording → compact panel
Stop recording → expanded review panel
Review finished → auto-dismiss


Auto-dismiss delay:


5–8 seconds


If the user interacts with the panel, the timer resets.

---

# Visual Style Summary

Design direction:


Minimal
Clean
Modern
Developer-focused
Fast


Influences:

- WhisperFlow
- Raycast
- Linear
- modern developer tools

The panel should feel like a **native productivity overlay**, not a traditional application window.

---

# Result

The recording panel becomes the central UI element of Glider.

It provides:

- clear recording state feedback
- real-time audio visualization
- mode awareness
- improved speech output
- vocabulary learning

This replaces intrusive notifications and transforms Glider into a **voice-first productivity and language improvement interface**.