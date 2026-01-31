#!/bin/bash
# Quick test script for Glaido

echo "Testing Glaido dependencies..."
echo ""

# Test Python imports
python3 -c "
import sounddevice as sd
import scipy
import groq
import numpy as np
from Xlib import X, XK
from Xlib.display import Display
print('✅ All core dependencies OK')
" 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Dependencies verified!"
    echo ""
    echo "Starting Glaido..."
    echo "Press Ctrl+Shift+Space to record"
    echo "Press Ctrl+C to exit"
    echo ""
    
    python3 ~/projects/glaido-free/glaido.py
else
    echo ""
    echo "❌ Missing dependencies. Install with:"
    echo "   pip install sounddevice scipy groq numpy python-xlib pystray Pillow"
fi
