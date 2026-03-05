"""
Visual test for rounded corners and transparency.
This script displays both panel states for visual verification.
"""

import tkinter as tk
import sys
import time
import threading
from recording_panel import PanelWindow, PanelState


def test_visual():
    """Show both panel states for visual verification."""

    def on_accept(text):
        print(f"[Visual Test] Accepted: {text[:50]}...")

    def on_reject(text):
        print(f"[Visual Test] Rejected: {text[:50]}...")

    # Create panel
    panel = PanelWindow(on_accept=on_accept, on_reject=on_reject)

    print("=" * 60)
    print("Visual Test - Recording Panel")
    print("=" * 60)
    print(f"Platform: {sys.platform}")
    print(f"Use transparent color: {getattr(panel, '_use_transparent_color', False)}")
    print(f"Transparent color: {panel.TRANSPARENT_COLOR}")
    print(f"BG Color: {panel.BG_COLOR}")
    print("=" * 60)

    # Show recording panel
    print("\n1. Showing RECORDING panel for 5 seconds...")
    panel.show_recording(mode_name="Dictation")

    # Simulate some time passing
    def show_processing():
        time.sleep(5)

        # Show processing
        print("\n2. Showing PROCESSING panel for 3 seconds...")
        panel.show_processing()
        time.sleep(3)

        # Show review panel
        print("\n3. Showing REVIEW panel for 10 seconds...")
        print("   (Press Enter to accept, Escape to reject)")
        panel.show_review(
            original_text="This is a test of the original text that might have some grammar issues.",
            improved_text="This is a test of the original text that might have some grammatical improvements.",
            mode_name="Dictation",
        )
        time.sleep(10)

        # Hide panel
        print("\n4. Hiding panel...")
        panel.hide()
        time.sleep(2)

        print("\nTest complete!")
        panel.destroy()

    # Run in separate thread so tkinter can process events
    thread = threading.Thread(target=show_processing, daemon=True)
    thread.start()

    # Start tkinter main loop
    if panel.root:
        panel.root.mainloop()


if __name__ == "__main__":
    test_visual()
