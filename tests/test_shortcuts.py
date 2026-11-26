import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from morse_input.acceptance import Session
from morse_input.app import App
from morse_input.morse import Timing


class ShortcutTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.root.attributes("-alpha", 0)
        with patch.object(App, "tick"):
            self.app = App(self.root, None, None, Timing())
        self.root.update()

    def press(self, widget, key):
        widget.focus_force()
        self.root.update()
        widget.event_generate(f"<KeyPress-{key}>")
        widget.event_generate(f"<KeyRelease-{key}>")
        self.root.update()

    def test_calibrate_then_delete(self):
        self.press(self.app.action, "space")
        self.assertTrue(self.app.recording)
        self.app.limits = [(0.2, 0.5)] * 2
        self.app.decoder.text = "AB"
        self.app.decoder.code = ".-"
        for key, expected in [("space", ("AB", ".")), ("BackSpace", ("AB", "")),
                              ("space", ("A", ""))]:
            self.press(self.root, key)
            self.assertEqual((self.app.decoder.text, self.app.decoder.code), expected)

    def test_learned_shortcuts_before_calibration(self):
        self.app.model = object()
        self.app.decoder.code = ".-"
        for key, expected in (("space", "."), ("BackSpace", "")):
            self.press(self.root, key)
            self.assertEqual(self.app.decoder.code, expected)
        self.assertFalse(self.app.recording)

    def test_space_on_focused_trial_button(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Session(self.root, self.app, Path(folder) / "trial.csv")
            self.app.limits = [(0.2, 0.5)] * 2
            self.app.decoder.code = "."
            self.press(session.button, "space")
            self.assertTrue(session.rehearsed)
            self.assertEqual(self.app.decoder.code, "")
            self.assertFalse(session.active)
            session.advance()
            self.app.decoder.text = "SOS"
            for key in ("space", "BackSpace"):
                self.press(session.button, key)
                self.assertEqual(self.app.decoder.text, "SOS")
                self.assertTrue(session.active)
                self.assertEqual(session.rows, [])
