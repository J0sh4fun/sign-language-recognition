"""Collect, train and compare a personal Morse model on fixed session splits."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import random
from tempfile import NamedTemporaryFile
import time

LAUNCHED = time.monotonic_ns() // 1_000_000

import numpy as np

from .gesture import calibrate, classify
from .morse import CODES, Timing
from .personal import BASE, MODEL, FEATURES, LABELS, Model, features, replay
from .trials import PHRASES, edits
from .paths import TIMING_CONFIG


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def save(path, value, *, replace=False):
    """Publish complete JSON atomically, refusing to overwrite collected trials."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False, mode="w", encoding="utf8") as f:
        temp = Path(f.name)
        try:
            json.dump(value, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        except BaseException:
            f.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        if replace:
            os.replace(temp, path)
        elif os.name == "nt":
            os.rename(temp, path)  # Windows refuses replacement of an existing path.
        else:
            os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def schedule(session):
    items = []
    if session <= 3:
        labels = list(LABELS) * 15
        random.Random(session).shuffle(labels)
        items.extend(("pose", label) for label in labels)
    if session >= 3:
        items.extend(("phrase", s) for s in PHRASES * (1 if session == 3 else 2))
    if session >= 4:
        items.extend(("calibration", s) for s in LABELS[:3])
    return items


def trial_path(base, session, i):
    return base / f"session-{session}" / f"{i+1:02}.json"


def records(base, session):
    for i, (kind, label) in enumerate(schedule(session)):
        path = trial_path(base, session, i)
        if kind == "calibration":
            path = path.parent / "calibration.json"
        if not path.exists():
            raise ValueError(f"Thiếu {path}. Hoàn thành phiên {session} trước.")
        r = read(path)
        if kind == "calibration":
            r = r[i-6]
        if (r["session"], r["trial"], r["kind"], r["label"]) != (session, i+1, kind, label):
            raise ValueError(f"Sai phiên, lượt hoặc nhãn trong {path}.")
        yield r


def fit(pose_trials):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    xs, ys, weights = [], [], []
    for r in pose_trials:
        samples = [v for _, p in r["frames"] if (v := features(p)) is not None]
        if not samples:
            raise ValueError(f"Lượt {r['trial']} thiếu tọa độ hợp lệ.")
        xs.extend(samples)
        ys.extend([r["label"]] * len(samples))
        weights.extend([1 / len(samples)] * len(samples))
    scaler = StandardScaler().fit(xs, sample_weight=weights)
    clf = LogisticRegression(max_iter=1000).fit(scaler.transform(xs), ys, sample_weight=weights)
    return dict(version=1, features=FEATURES, labels=clf.classes_.tolist(), mean=scaler.mean_.tolist(),
                scale=scaler.scale_.tolist(), coef=clf.coef_.tolist(), bias=clf.intercept_.tolist(),
                threshold=.6)


def false_marks(target, actual):
    """Minimum edit alignment; count inserted/substituted emitted marks on ties."""
    row = [(j, j) for j in range(len(actual)+1)]
    for i, a in enumerate(target, 1):
        nxt = [(i, 0)]
        for j, b in enumerate(actual, 1):
            change = int(a != b)
            nxt.append(min((row[j][0]+1, row[j][1]), (nxt[-1][0]+1, nxt[-1][1]+1),
                           (row[j-1][0]+change, row[j-1][1]+change)))
        row = nxt
    return row[-1][1]


def score_phrase(r, classifier, timing):
    out = replay(r["frames"], classifier, timing, r.get("delete_after_frames", ()))
    target = r["label"]
    out["errors"] = edits(target, out["text"])
    out["false_marks"] = false_marks("".join(CODES[c] for c in target if c != " "), out["marks"])
    out["target"] = target
    return out


def train(base, timing):
    spec = fit(r for s in (1, 2) for r in records(base, s))
    validation = list(records(base, 3))
    model = Model(spec)
    matrix = {label: dict.fromkeys(LABELS, 0) for label in LABELS}
    for r in validation:
        if r["kind"] == "pose":
            for _, p in r["frames"]:
                if (x := features(p)) is not None:
                    matrix[r["label"]][model.prediction(x)[0]] += 1
    sweep = []
    for percent in range(60, 91, 5):
        model.threshold = percent / 100
        phrases = [score_phrase(r, model.classify, timing) for r in validation if r["kind"] == "phrase"]
        sweep.append(dict(threshold=model.threshold, errors=sum(p["errors"] for p in phrases),
                          false_marks=sum(p["false_marks"] for p in phrases), phrases=phrases))
    best = min(sweep, key=lambda s: (s["errors"], s["false_marks"], s["threshold"]))
    spec.update(threshold=best["threshold"], timing=asdict(timing))
    save(base / "validation.json", dict(confusion=matrix, sweep=sweep, selected=best), replace=True)
    save(base / MODEL, spec)
    return best


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(base):
    model = Model.load(base / MODEL)
    digest = fingerprint(base / MODEL)
    timing = Timing(**read(base / MODEL)["timing"])
    all_rows, sessions = [], []
    for session in (4, 5):
        rows = list(records(base, session))
        if any(r["model_sha256"] != digest for r in rows):
            raise ValueError("Phiên nghiệm thu dùng mô hình khác.")
        limits = calibrate([[features(p)[:2] for _, p in r["frames"]]
                            for r in rows if r["kind"] == "calibration"])
        first_ms = rows[0]["startup_first_ms"]
        demo = False
        for r in rows[:6]:
            learned = score_phrase(r, model.classify, timing)
            old = score_phrase(r, lambda x: classify(x[:2] if x is not None else None, limits), timing)
            if learned["text"] != r["live_text"] or learned["pending"] != r["live_pending"]:
                raise ValueError("Kết quả phát lại khác kết quả trực tiếp.")
            duration = (learned["last_letter_ms"] - learned["first_ms"]
                        if learned["last_letter_ms"] is not None else 0)
            demo |= learned["text"] == r["label"] == "SOS 2026" and not learned["pending"]
            all_rows.append(dict(session=session, trial=r["trial"], learned=learned, calibrated=old,
                                 deletions=len(r.get("delete_after_frames", ())),
                                 typing_chars_min=60000*len(learned["text"])/duration if duration else None))
        sessions.append(dict(session=session, startup_first_ms=first_ms, sos_ok=demo,
                             controls_ok=rows[0]["controls_ok"], learned_calibrations=0))
    ai = sum(r["learned"]["errors"] for r in all_rows)
    baseline = sum(r["calibrated"]["errors"] for r in all_rows)
    passed = (ai <= 4 and ai <= baseline + 2 and
              all(s["controls_ok"] and s["sos_ok"] and s["startup_first_ms"] is not None for s in sessions))
    report = dict(model_sha256=digest, sessions=sessions, trials=all_rows, target_chars=80,
                  learned_errors=ai, calibrated_errors=baseline, learned_cer=ai/80, passed=passed)
    save(base / "acceptance.json", report, replace=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "train", "compare"))
    parser.add_argument("session", nargs="?", type=int, choices=range(1, 6))
    parser.add_argument("--data", type=Path, default=BASE)
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()
    base = args.data
    try:
        timing = Timing(**read(TIMING_CONFIG))
        if args.command == "collect":
            if args.session is None:
                parser.error("Chọn phiên 1–5.")
            from .capture_session import start
            start(base, args.session, args.camera, timing, LAUNCHED)
        elif args.command == "train":
            if (base / MODEL).exists():
                raise ValueError("Mô hình đã khóa. Dùng thư mục --data mới cho đợt thử mới.")
            best = train(base, timing)
            print(f"Đã lưu {base / MODEL}. Ngưỡng {best['threshold']}, lỗi phiên 3: {best['errors']}.")
        else:
            result = compare(base)
            print(f"AI {result['learned_errors']}/80, đối chứng {result['calibrated_errors']}/80. "
                  f"Đạt: {result['passed']}. {base / 'acceptance.json'}")
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
