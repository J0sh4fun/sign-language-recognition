"""Portable personal classifier, landmark features and deterministic playback."""
import json
from math import dist

import numpy as np

from .morse import Decoder, Timing

from .paths import PERSONAL_DATA as BASE
MODEL = "model-v1.json"
LABELS = ("open", "dot", "dash", "both")
PAIRS = ((4, 8), (4, 12), (8, 12), (8, 0), (12, 0))
FEATURES = [f"{a}-{b}/5-17" for a, b in PAIRS]
GAP_MS = 350


def features(points):
    if points is None:
        return None
    palm = dist(points[5][:2], points[17][:2])
    if palm < 1:
        return None
    return [dist(points[a][:2], points[b][:2]) / palm for a, b in PAIRS]


class Model:
    def __init__(self, spec):
        if (spec["version"] != 1 or spec["features"] != FEATURES or
                sorted(spec["labels"]) != sorted(LABELS)):
            raise ValueError("Phiên bản, đặc trưng hoặc nhãn mô hình không phù hợp.")
        self.labels = spec["labels"]
        for key, shape in (("mean", (5,)), ("scale", (5,)), ("coef", (4, 5)), ("bias", (4,))):
            array = np.asarray(spec[key], dtype=float)
            if array.shape != shape or not np.all(np.isfinite(array)):
                raise ValueError(f"Tham số mô hình không hợp lệ: {key}")
            setattr(self, key, array)
        self.threshold = float(spec["threshold"])
        self.timing = Timing(**spec.get("timing", {}))
        if np.any(self.scale <= 0) or not 0 < self.threshold <= 1:
            raise ValueError("Tỷ lệ chuẩn hóa hoặc ngưỡng không hợp lệ.")

    @classmethod
    def load(cls, path):
        try:
            spec = json.loads(path.read_text(encoding="utf8"))
            if "timing" not in spec:
                raise ValueError("Thiếu cấu hình thời gian đã khóa.")
            return cls(spec)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"Không đọc được {path}: {exc}. Chạy python experiment.py train "
                             "sau phiên 3, hoặc dùng python app.py để hiệu chuẩn.") from exc

    def prediction(self, x):
        scores = self.coef @ ((x - self.mean) / self.scale) + self.bias
        probabilities = np.exp(scores - scores.max())
        i = int(scores.argmax())
        return self.labels[i], probabilities[i] / probabilities.sum()

    def classify(self, x):
        if x is None:
            return "unknown"
        label, confidence = self.prediction(x)
        if label == "both":
            return "unknown"
        return label if confidence >= self.threshold else "transition"


def replay(frames, classifier, timing, delete_after_frames=()):
    decoder = Decoder(timing)
    marks = []
    first = last_letter = previous = None
    next_delete = iter(delete_after_frames)
    boundary = next(next_delete, None)
    for index in range(len(frames) + 1):
        while boundary == index:
            decoder.backspace()
            boundary = next(next_delete, None)
        if index == len(frames):
            break
        now, points = frames[index]
        if previous is not None:
            if now <= previous:
                raise ValueError("Thời gian khung hình phải tăng dần.")
            if now - previous > GAP_MS:
                decoder.interrupt()
        previous = now
        events = decoder.observe(classifier(features(points)), now)
        for event in events:
            if event in ("dot", "dash"):
                marks.append("." if event == "dot" else "-")
                if first is None:
                    first = now
            elif event == "letter":
                last_letter = now
    if boundary is not None:
        raise ValueError("Vị trí thao tác xóa trong lượt thu không hợp lệ.")
    return dict(text=decoder.text, marks="".join(marks), pending=decoder.code,
                first_ms=first, last_letter_ms=last_letter)
