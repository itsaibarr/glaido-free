# Glaido English Improvement System

## Overview

The English Improvement System improves voice transcriptions by using an LLM (Groq API) to fix grammar, vocabulary, and sentence structure while keeping the original meaning.

## How It Works

### 1. Transcription Flow

1. User speaks → Audio recorded
2. Audio sent to Whisper API (STT)
3. Raw transcription received
4. **English Improvement** (if enabled) → Text sent to LLM for refinement
5. Review panel shows original vs improved text
6. User accepts or rejects improvements
7. Final text output to clipboard/typing

### 2. Integration

The system connects to the main Glaido workflow in [`glaido.py`](glaido.py:608):

```python
# Processing Layer (mode switch)
result = self.processor.process(text, improve_english=True)
original = result["original"]
improved = result["improved"]

# Show review panel with diff
self.panel.show_review(original, improved)
```

## Implementation Details

### System Prompt

Located at [`glaido.py`](glaido.py:78-87):

```python
ENGLISH_IMPROVEMENT_INSTRUCTION = (
    "You are an English language expert. Improve the following text by:\n"
    "1. Fixing grammar errors\n"
    "2. Using better vocabulary\n"
    "3. Improving sentence structure\n"
    "4. Keeping the original meaning\n"
    "\n"
    "Return ONLY the improved text, no explanations."
)
```

### Processing Layer

The [`ProcessingLayer._improve_english()`](glaido.py:314-331) method:

- Sends text to Groq API (llama-3.3-70b-versatile)
- Uses temperature=0.3 for consistent results
- Returns improved text or falls back to original on error

### Review Panel

The [`recording_panel.py`](recording_panel.py:837-910) provides:

- **Original Text Section**: Shows raw transcription
- **Improved Text Section**: Shows LLM-enhanced version with diff highlighting
- **Key Improvements**: Lists specific changes made (e.g., "'i think' → 'I believe'")
- **Accept/Reject Controls**: Keyboard (Enter/Escape) or button clicks

### Diff Highlighting

Word-level diff visualization using Python's `difflib.SequenceMatcher`:

- **Green (added)**: New words/phrases in improved version
- **Red (removed)**: Words/phrases that were changed
- **No highlight**: Unchanged text

## User Experience

### Recording

- Press `Ctrl+Shift+Space` to start recording
- Recording panel appears with timer and waveform

### Processing

- After stopping recording, panel shows "Processing..."
- Transcription and improvement happen in background thread

### Review

- Panel expands to show original vs improved comparison
- User can:
  - Press `Enter` to accept improved version
  - Press `Escape` to reject and use original
- Selected text is automatically typed/pasted

## Configuration

The English Improvement is **always enabled** for transcribe mode. There is no user-facing toggle currently.

## Mode Behavior

### Transcribe Mode
- Raw speech → English Improvement → Review Panel → Output

### Prompt Mode
- Raw speech → Prompt Optimization (no English Improvement) → Output

## Error Handling

If the LLM call fails:
1. Error is logged to console
2. Original transcription is used as fallback
3. User sees review panel with identical original/improved text
4. User can still accept/reject as normal

## Dependencies

- `groq` Python package
- Groq API key (set in `.env` file)
- Model: `llama-3.3-70b-versatile`

## Future Enhancements

Possible improvements to consider:

1. **Toggle Setting**: Allow users to disable English Improvement
2. **Language Selection**: Support improvement for other languages
3. **Style Presets**: Formal, casual, technical writing styles
4. **Custom Instructions**: User-defined improvement preferences
5. **Learning Mode**: Track common mistakes and provide tips
