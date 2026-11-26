import unittest
from types import SimpleNamespace

from morse_input.gesture import calibrate, classify, measure
from morse_input.morse import CODES, Decoder


class GestureTests(unittest.TestCase):
    def test_calibration_and_classification(self):
        limits = calibrate([[(1, 1)] * 3, [(.1, 1)] * 3, [(1, .1)] * 3])
        for pair, expected in [(None, "unknown"), ((.2, .2), "unknown"),
                               ((1, 1), "open"), ((.2, .9), "dot"),
                               ((1, .2), "dash"), ((.5, .8), "transition")]:
            self.assertEqual(classify(pair, limits), expected)
        with self.assertRaisesRegex(ValueError, "cái–trỏ"):
            calibrate([[(1, 1)], [(1, 1)], [(1, .1)]])

    def test_pixel_distances(self):
        points = [SimpleNamespace(x=0, y=0) for _ in range(21)]
        self.assertIsNone(measure(points, 640, 480))
        points[17].x, points[8].y, points[12].x = .5, .5, .25
        self.assertEqual(measure(points, 640, 480), (.75, .5))


class DecoderTests(unittest.TestCase):
    def setUp(self):
        self.d = Decoder()
        self.feed = self.d.observe
        self.feed("open", 0)
        self.feed("open", 100)

    def test_messages(self):
        for msg in ["S", "EE", "E E", "A", "N", "SOS 2026", "AN NA", "EEE TTT", "".join(CODES)]:
            with self.subTest(msg=msg):
                d = Decoder()
                now = 0
                for char in msg:
                    if char == " ":
                        now += 1500
                        d.observe("open", now)
                        continue
                    for symbol in CODES[char]:
                        pose = "dot" if symbol == "." else "dash"
                        d.observe("open", now)
                        d.observe("open", now + 100)
                        d.observe(pose, now + 160)
                        d.observe(pose, now + 310)
                        now += 400
                    d.observe("open", now)
                    now += 1000
                    d.observe("open", now)
                self.assertEqual(d.text, msg)

    def test_hold_release(self):
        self.feed("dot", 101)
        self.assertEqual(self.feed("dot", 250), [])
        self.assertEqual(self.feed("dot", 251), ["dot"])
        self.feed("dot", 2251)
        self.feed("open", 2300)
        self.feed("dash", 2399)
        self.feed("dash", 2700)
        self.assertEqual(self.d.code, ".")
        self.feed("open", 2800)
        self.feed("open", 2900)
        self.feed("dash", 2910)
        self.feed("dash", 3060)
        self.assertEqual(self.d.code, ".-")

    def start_letter(self):
        self.feed("dot", 200)
        self.feed("dot", 350)
        self.feed("open", 400)

    def test_boundaries(self):
        self.start_letter()
        self.assertEqual(self.feed("open", 1399), [])
        self.assertEqual(self.feed("open", 1400), ["letter"])
        self.assertEqual(self.feed("open", 2899), [])
        self.assertEqual(self.feed("open", 2900), ["word"])
        self.assertEqual(self.feed("open", 5000), [])
        self.assertEqual(self.d.text, "E")

    def test_pinch_at_950(self):
        self.start_letter()
        self.feed("open", 1300)
        self.feed("dash", 1350)
        self.feed("dash", 1500)
        self.assertEqual((self.d.text, self.d.code), ("", ".-"))

    def test_lost_hand_and_ambiguous_pose(self):
        self.feed("dot", 200)
        self.feed("unknown", 310)
        self.feed("dot", 600)
        self.assertEqual(self.d.code, "")
        self.feed("open", 700)
        self.feed("open", 800)
        self.feed("dot", 900)
        self.feed("dot", 1050)
        self.feed("open", 1100)
        self.feed("unknown", 2080)
        self.feed("unknown", 7000)
        self.assertEqual((self.d.code, self.d.text), (".", ""))
        self.feed("open", 7200)
        self.feed("open", 8199)
        self.assertEqual(self.d.text, "")
        self.feed("open", 8200)
        self.assertEqual(self.d.text, "E")
        self.assertFalse(self.d.word_pending)

    def test_invalid_and_edit(self):
        self.d.code = "......"
        self.feed("open", 1200)
        self.assertTrue(self.d.error)
        self.assertEqual(self.d.code, "......")
        self.d.backspace()
        self.feed("open", 1500)
        self.feed("open", 2500)
        self.assertEqual(self.d.text, "5")
        self.d.backspace()
        self.assertEqual(self.d.text, "")
