"""Exercise the five-session workflow with synthetic landmarks only."""
from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk
import unittest
from unittest.mock import patch

from morse_input.app import App
from morse_input.capture_session import Recorder
from morse_input.experiment import (compare, fingerprint, fit, read, records, save, schedule, train,
                        trial_path)
from morse_input.morse import CODES, Timing
from morse_input.personal import MODEL, Model, features, replay


def hand(pose):
    points = [[0., 0., 0.] for _ in range(21)]
    points[17][0] = 100
    points[4] = [0, 90, 0]
    points[8] = [5 if pose in ("dot", "both") else 100, 90, 0]
    points[12] = [-5 if pose in ("dash", "both") else -100, 90, 0]
    return points


def message_frames(text):
    frames = []

    def hold(pose, n):
        for _ in range(n):
            frames.append([len(frames)*50, hand(pose) if pose else None])

    hold(None, 2)
    hold("open", 4)
    for c in text:
        if c == " ":
            hold("open", 54)
            continue
        for symbol in CODES[c]:
            hold("dot" if symbol == "." else "dash", 5)
            hold("open", 4)
        hold("open", 21)
    return frames


class PersonalTests(unittest.TestCase):
    def test_five_sessions(self):
        with TemporaryDirectory() as directory:
            self.pipeline(Path(directory))

    def pipeline(self, base):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        timing = Timing()
        model = None
        for s in range(1, 6):
            digest = fingerprint(base / MODEL) if s >= 4 else None
            if s == 3:
                model = Model(fit(r for i in (1, 2) for r in records(base, i)))
            with patch.object(App, "tick"):
                ui = Recorder(root, None, None, timing, model, base, s, 0, digest)
            for i, (kind, label) in enumerate(schedule(s)):
                self.assertEqual(ui.task, (kind, label))
                with patch("morse_input.capture_session.messagebox.askyesno", return_value=True):
                    ui.advance()
                if kind == "phrase":
                    offset = 0
                    if s >= 4 and i == 0:
                        for ts, points in message_frames("EE"):
                            ui.process_frame(points, ui.start_ms + ts)
                        self.assertEqual(ui.decoder.text, "EE")
                        ui.on_key(None)
                        ui.on_key(None)
                        self.assertEqual(ui.decoder.text, "")
                        offset = ts + 50
                    for ts, points in message_frames(label):
                        ui.process_frame(points, ui.start_ms + offset + ts)
                    self.assertEqual(ui.decoder.text, label)
                else:
                    for ts in range(0, 2050, 50):
                        ui.process_frame(hand(label), ui.start_ms + ts)
                    self.assertEqual(ui.phase, "review")
                    if i == 0:
                        ui.repeat()
                        self.assertFalse(trial_path(base, s, 0).exists())
                        ui.advance()
                        for ts in range(0, 2050, 50):
                            ui.process_frame(hand(label), ui.start_ms + ts)
                with patch.object(root, "destroy"), patch("morse_input.capture_session.messagebox.showinfo"):
                    ui.advance()
            if s == 3:
                selected = train(base, timing)
                self.assertEqual((selected["errors"], selected["threshold"]), (0, .6))
                model = Model.load(base / MODEL)
                before = replay(message_frames("AN NA"), model.classify, timing)
                self.assertEqual(before, replay(message_frames("AN NA"), model.classify, timing))
                model.threshold = 1
                self.assertEqual(model.classify(features(hand("dot"))), "transition")
                self.assertEqual(model.classify(features(hand("both"))), "unknown")
                self.assertEqual(model.classify(None), "unknown")
                model = Model.load(base / MODEL)
        result = compare(base)
        self.assertTrue(result["passed"])
        self.assertEqual((result["target_chars"], result["learned_errors"], result["calibrated_errors"]),
                         (80, 0, 0))
        self.assertEqual(len(result["trials"]), 12)
        self.assertEqual(sum(r["deletions"] for r in result["trials"]), 4)
        self.assertTrue(all(r["typing_chars_min"] > 0 for r in result["trials"]))
        with self.assertRaises(FileExistsError):
            save(base / MODEL, {})
        spec = read(base / MODEL)
        spec["version"] = 2
        save(base / "invalid.json", spec)
        for name in ("missing", "invalid.json"):
            with self.assertRaisesRegex(ValueError, "experiment.py train"):
                Model.load(base / name)

    def test_require_release_and_interrupt_on_frame_gap(self):
        observations = [[0, hand("dot")], [200, hand("dot")], [250, hand("open")],
                        [400, hand("open")], [450, hand("dot")], [1000, hand("dot")]]
        out = replay(observations, lambda x: "dot" if x[0] < .5 else "open", Timing())
        self.assertEqual(out["marks"], "")
