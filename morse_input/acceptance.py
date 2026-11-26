"""One-person webcam acceptance session. Raw images are never saved."""
import csv
from contextlib import redirect_stdout
from datetime import datetime
import io
import json
import time
import tkinter as tk
from tkinter import messagebox, ttk

import cv2

from .app import App, landmarker
from .paths import RESULTS, TIMING_CONFIG
from .morse import Decoder, Timing
from .trials import FIELDS, KEYS, report


class Session:
    def __init__(self, root, app, path):
        self.root, self.app, self.path = root, app, path
        self.rows = []
        self.keys = [k for k in KEYS if k[0] == "P1"]
        self.active = False
        self.rehearsed = False
        self.label = tk.StringVar(value="Hiệu chuẩn rồi nhập thử E. Nhấn Space hoặc Backspace để sửa trong lượt làm quen.")
        ttk.Label(root, textvariable=self.label, wraplength=760).pack()
        self.button = ttk.Button(root, text="Bắt đầu đo", command=self.advance)
        self.button.pack(pady=4)
        app.delete_last = self.correct
        # Handle Space before Tk's button class can start or finish a trial.
        self.button.bind("<space>", app.on_key)
        with path.open("x", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerow(FIELDS)

    def correct(self):
        decoder = self.app.decoder
        if not self.rows and not self.active and (decoder.text or decoder.code):
            decoder.backspace()
            self.rehearsed = True
            self.label.set("Đã sửa. Lượt 1 sẽ nhập SOS 2026. Nhấn Bắt đầu đo khi sẵn sàng.")

    def advance(self):
        if not self.app.input_ready or not self.rehearsed:
            self.label.set("Hoàn tất hiệu chuẩn, nhập thử một dấu rồi nhấn Space hoặc Backspace trước khi đo.")
            return
        i = len(self.rows)
        person, phrase, attempt = self.keys[i]
        if not self.active:
            self.app.decoder = Decoder(self.app.decoder.timing)
            self.label.set(f"Lượt {i+1}/6 · Nhập {phrase} · Chờ chốt chữ cuối rồi nhấn Kết thúc lượt.")
            self.button.config(text="Kết thúc lượt")
            self.start = time.monotonic()
            self.active = True
            return
        decoder = self.app.decoder
        if decoder.code and not decoder.error:
            self.label.set(f"Đang nhập {phrase}. Tách ngón và chờ chốt chữ cuối trước khi kết thúc.")
            return
        elapsed = time.monotonic() - self.start
        row = dict(person=person, phrase=phrase, attempt=attempt, raw_text=decoder.text,
                   seconds=f"{elapsed:.3f}", notes=f"Mã còn lại: {decoder.code}" if decoder.code else "")
        with self.path.open("a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writerow(row)
        self.rows.append(row)
        self.active = False
        if len(self.rows) < len(self.keys):
            self.label.set(f"Đã lưu lượt {i+1}. Tiếp theo: {self.keys[i+1][1]}. Nhấn bắt đầu khi sẵn sàng.")
            self.button.config(text="Bắt đầu lượt tiếp")
        else:
            summary = io.StringIO()
            with redirect_stdout(summary):
                report(self.rows, ("P1",))
            messagebox.showinfo("Kết quả nghiệm thu P1", summary.getvalue())
            self.root.destroy()


def main():
    timing = Timing(**json.loads(TIMING_CONFIG.read_text(encoding="utf8")))
    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    try:
        if not cam.isOpened():
            raise SystemExit("Không mở được webcam 0.")
        with landmarker() as tracker:
            root = tk.Tk()
            app = App(root, cam, tracker, timing)
            root.title("Nghiệm thu Morse · 1 người")
            directory = RESULTS
            directory.mkdir(exist_ok=True)
            path = directory / datetime.now().strftime("P1-%Y%m%d-%H%M%S.csv")
            session = Session(root, app, path)
            root.mainloop()
    finally:
        cam.release()


if __name__ == "__main__":
    main()
