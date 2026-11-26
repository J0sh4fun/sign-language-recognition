"""Gesture timing and International Morse decoding, independent of the camera."""
from dataclasses import dataclass


CODES = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", (
    ".- -... -.-. -.. . ..-. --. .... .. .--- -.- .-.. -- -. --- .--. "
    "--.- .-. ... - ..- ...- .-- -..- -.-- --.. "
    "----- .---- ..--- ...-- ....- ..... -.... --... ---.. ----."
).split(), strict=True))
LETTERS = {code: letter for letter, code in CODES.items()}


@dataclass(frozen=True)
class Timing:
    hold_ms: int = 150
    release_ms: int = 100
    letter_ms: int = 1000
    word_ms: int = 2500

    def __post_init__(self):
        if not (self.hold_ms > 0 and 0 < self.release_ms < self.letter_ms < self.word_ms):
            raise ValueError("Cần hold_ms > 0 và 0 < release_ms < letter_ms < word_ms.")


class Decoder:
    def __init__(self, timing=Timing()):
        self.timing = timing
        self.code = ""
        self.text = ""
        self.error = False
        self.word_pending = False
        self.interrupt()

    def interrupt(self):
        self.ready = False
        self.rest_start = None
        self.candidate = None
        self.elapsed = 0
        self.state = "Hãy tách ngón"

    def backspace(self):
        if self.code:
            self.code = self.code[:-1]
        else:
            self.text = self.text[:-1].rstrip()
            self.word_pending = False
        self.error = False
        self.interrupt()

    def _rest(self, now):
        events = []
        if self.rest_start is None:
            self.rest_start = now
        self.elapsed = now - self.rest_start
        if self.elapsed >= self.timing.release_ms:
            self.ready = True
            self.state = "Sẵn sàng"
        if self.elapsed >= self.timing.letter_ms and self.code and not self.error:
            letter = LETTERS.get(self.code)
            if letter is None:
                self.error = True
            else:
                self.text += (" " if self.word_pending else "") + letter
                self.code = ""
                self.word_pending = False
                events.append("letter")
        if (self.elapsed >= self.timing.word_ms and self.text and
                not self.code and not self.word_pending):
            self.word_pending = True
            events.append("word")
        return events

    def observe(self, pose, now):
        """Consume open, dot, dash, transition or unknown at monotonic ms."""
        if pose == "unknown":
            self.interrupt()
            return []
        if pose == "open":
            self.candidate = None
            return self._rest(now)
        events = self._rest(now) if self.rest_start is not None else []
        self.rest_start = None
        self.elapsed = 0
        if pose == "transition" or not self.ready or self.error:
            self.candidate = None
            return events
        if self.candidate != pose:
            self.candidate = pose
            self.since = now
            self.state = "Đang nhận dấu"
        if now - self.since >= self.timing.hold_ms:
            self.code += "." if pose == "dot" else "-"
            self.ready = False
            self.state = "Đã nhận dấu"
            events.append(pose)
        return events
