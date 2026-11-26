"""Create or score the 18 accuracy trials; keep raw text including spaces."""
import argparse
import csv
from pathlib import Path

PHRASES = ("SOS 2026", "AN NA", "EEE TTT")
FIELDS = ("person", "phrase", "attempt", "raw_text", "seconds",
          "wrong_pair", "repeated_mark", "early_commit", "notes")
KEYS = [(p, s, str(i)) for p in ("P1", "P2", "P3") for s in PHRASES for i in (1, 2)]


def edits(expected, actual):
    row = list(range(len(actual) + 1))
    for i, left in enumerate(expected, 1):
        following = [i]
        for j, right in enumerate(actual, 1):
            following.append(min(row[j] + 1, following[-1] + 1, row[j-1] + (left != right)))
        row = following
    return row[-1]


def report(rows, people=("P1", "P2", "P3")):
    keys = [key for key in KEYS if key[0] in people]
    indexed = {(r["person"], r["phrase"], r["attempt"]): r for r in rows}
    if len(rows) != len(keys) or set(indexed) != set(keys):
        raise ValueError(f"Cần đủ {len(keys)} lượt theo mẫu, mỗi lượt một dòng.")
    errors = total = 0
    all_demo = True
    for person in people:
        count = length = typed = 0
        elapsed = 0.0
        demo = False
        for key in (k for k in KEYS if k[0] == person):
            r = indexed[key]
            raw, target = r["raw_text"], r["phrase"]
            if not r["seconds"] or not (0 < float(r["seconds"]) < float("inf")):
                raise ValueError(f"Thiếu thời gian dương cho {key}.")
            elapsed += float(r["seconds"])
            typed += len(raw)
            count += edits(target, raw)
            length += len(target)
            demo |= target == raw == "SOS 2026"
        errors += count
        total += length
        all_demo &= demo
        print(f"{person}: CER {count/length:.1%}, {60*typed/elapsed:.1f} ký tự/phút, SOS đúng: {demo}")
    print(f"CER gộp: {errors}/{total} = {errors/total:.1%}. Đạt mục tiêu nhập: {all_demo and errors/total <= .1}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("new", "score"))
    parser.add_argument("file", type=Path)
    parser.add_argument("--one", action="store_true", help="Chỉ nghiệm thu P1")
    args = parser.parse_args()
    try:
        if args.action == "new":
            with args.file.open("x", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(FIELDS)
                writer.writerows((*key, "", "", "", "", "", "") for key in KEYS if not args.one or key[0] == "P1")
        else:
            with args.file.open(encoding="utf-8-sig", newline="") as f:
                report(list(csv.DictReader(f)), ("P1",) if args.one else ("P1", "P2", "P3"))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
