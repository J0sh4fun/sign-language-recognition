"""Run the local webcam prototype with python app.py."""
import argparse
import json
import sys
from pathlib import Path
import time
import tkinter as tk
from tkinter import messagebox, ttk

import cv2
import mediapipe as mp
from PIL import Image, ImageTk

from .gesture import calibrate, classify
from .morse import CODES, Decoder, Timing
from .personal import BASE, MODEL, GAP_MS, Model, features

from .paths import HAND_MODEL, TIMING_CONFIG
POSES = ("Tách ngón cái khỏi cả ngón trỏ và ngón giữa",
         "Chụm cái–trỏ, tách ngón giữa", "Chụm cái–giữa, tách ngón trỏ")


def landmarker():
    vision = mp.tasks.vision
    options = vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(HAND_MODEL)),
        running_mode=vision.RunningMode.VIDEO, num_hands=1)
    return vision.HandLandmarker.create_from_options(options)


def analyze(frame, tracker, now):
    rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    result = tracker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), now)
    landmarks = None
    if result.hand_landmarks:
        points = result.hand_landmarks[0]
        landmarks = [[p.x * width, p.y * height, p.z * width] for p in points]
        for i, color in ((4, (255, 210, 60)), (8, (70, 240, 140)), (12, (90, 190, 255))):
            center = int(points[i].x * width), int(points[i].y * height)
            cv2.circle(rgb, center, 7, color, -1)
    image = Image.fromarray(rgb)
    image.thumbnail((640, 440))
    return image, landmarks


class App:
    def __init__(self, root, camera, tracker, timing, model=None):
        self.root, self.camera, self.tracker = root, camera, tracker
        self.decoder = Decoder(timing)
        self.model = model
        self.last_frame = None
        self.limits = None
        self.samples = []
        self.recording = False
        self.batch = []
        self.started = None
        root.title("Nhập Morse bằng ngón tay")
        panel = ttk.Frame(root, padding=12)
        panel.pack()
        self.preview = ttk.Label(panel)
        self.preview.grid(row=0, column=0)
        guide = ttk.Frame(panel, padding=10)
        guide.grid(row=0, column=1, sticky="n")
        ttk.Label(guide, text="Bảng Morse").pack()
        entries = [f"{c} {code:<5}" for c, code in CODES.items()]
        table = "\n".join("  ".join(row) for row in zip(entries[:18], entries[18:]))
        ttk.Label(guide, text=table, font=("Consolas", 11)).pack()
        self.status = tk.StringVar()
        self.code = tk.StringVar()
        self.text = tk.StringVar()
        for row, (var, size) in enumerate(((self.status, 12), (self.code, 16), (self.text, 18)), 1):
            ttk.Label(panel, textvariable=var, font=("Segoe UI", size), wraplength=780).grid(
                row=row, column=0, columnspan=2, sticky="w")
        self.bar = ttk.Progressbar(panel, maximum=timing.word_ms)
        self.bar.grid(row=4, column=0, columnspan=2, sticky="ew", pady=6)
        self.action = ttk.Button(panel, text="Thu tư thế (Space)", command=self.capture)
        self.action.grid(row=5, column=0, sticky="w")
        ttk.Label(panel, text="Cái–trỏ  ·    Cái–giữa  −    Space / Backspace  Xóa khi nhập    Esc  Thoát").grid(
            row=6, column=0, columnspan=2, sticky="w")
        self.action.bind("<space>", self.on_key)
        root.bind("<space>", self.on_key)
        root.bind("<BackSpace>", self.on_key)
        root.bind("<Escape>", lambda e: root.destroy())
        if self.model is None:
            self.prompt()
        else:
            self.action.grid_remove()
            self.status.set("Mô hình cá nhân · Hãy tách ngón để bắt đầu")
        root.after(1, self.tick)

    def delete_last(self):
        self.decoder.backspace()

    @property
    def input_ready(self):
        return self.model is not None or self.limits is not None

    def on_key(self, event):
        if self.input_ready:
            self.delete_last()
        elif event.keysym == "space":
            self.capture()
        return "break"

    def prompt(self, prefix=""):
        self.status.set(f"{prefix}Hiệu chuẩn {len(self.samples)+1}/3 · {POSES[len(self.samples)]}. Nhấn Space.")

    def capture(self):
        if not self.input_ready and not self.recording:
            self.recording = True
            self.started = None
            self.batch = []

    def collect(self, pair, now):
        if pair is None:
            self.batch.clear()
            self.started = None
            self.status.set("Chưa thấy bàn tay. Đưa tay vào khung để thu lại tư thế.")
            return
        if self.started is None:
            self.started = now
        self.batch.append(pair)
        elapsed = now - self.started
        self.status.set(f"{POSES[len(self.samples)]} · Giữ yên {min(elapsed, 1000)/1000:.1f}/1 giây")
        if elapsed < 1000:
            return
        self.samples.append(self.batch)
        self.recording = False
        if len(self.samples) < 3:
            self.prompt()
            return
        try:
            self.limits = calibrate(self.samples)
        except ValueError as exc:
            self.samples.clear()
            self.prompt(f"{exc} ")
        else:
            self.action.grid_remove()

    def tick(self):
        ok, frame = self.camera.read()
        if not ok:
            messagebox.showerror("Webcam", "Mất kết nối webcam. Kiểm tra camera và mở lại ứng dụng.")
            self.root.destroy()
            return
        now = time.monotonic_ns() // 1_000_000
        if self.last_frame is not None and now - self.last_frame > GAP_MS:
            self.decoder.interrupt()
            self.batch = []
            self.started = None
        self.last_frame = now
        image, points = analyze(frame, self.tracker, now)
        self.photo = ImageTk.PhotoImage(image)
        self.preview.configure(image=self.photo)
        self.process_frame(points, now)
        self.root.after(10, self.tick)

    def process_frame(self, points, now):
        x = features(points)
        pair = x[:2] if x is not None else None
        if self.input_ready:
            decoder = self.decoder
            pose = self.model.classify(x) if self.model else classify(pair, self.limits)
            events = decoder.observe(pose, now)
            self.status.set("Mã chưa hợp lệ · Dùng phím xóa để sửa" if decoder.error else decoder.state)
            self.code.set(f"Dấu đang nhập   {decoder.code}")
            self.text.set(f"Văn bản   {decoder.text}")
            self.bar["value"] = min(decoder.elapsed, decoder.timing.word_ms)
            return events
        elif self.recording:
            self.collect(pair, now)
        return []


def run_camera(index, build):
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    camera = cv2.VideoCapture(index, backend)
    if not camera.isOpened() and backend != cv2.CAP_ANY:
        camera.release()
        camera = cv2.VideoCapture(index)
    try:
        if not camera.isOpened():
            raise ValueError(f"Không mở được webcam {index}. Kiểm tra quyền camera hoặc thử --camera 1.")
        with landmarker() as tracker:
            root = tk.Tk()
            build(root, camera, tracker)
            root.mainloop()
    finally:
        camera.release()


def main():
    parser = argparse.ArgumentParser(description="Nhập Morse bằng webcam")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--mode", choices=("calibrated", "learned"), default="calibrated")
    parser.add_argument("--model", type=Path, default=BASE / MODEL)
    args = parser.parse_args()
    try:
        model = Model.load(args.model) if args.mode == "learned" else None
        timing = model.timing if model else Timing(**json.loads(TIMING_CONFIG.read_text(encoding="utf8")))
        run_camera(args.camera, lambda root, cam, tracker: App(root, cam, tracker, timing, model))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
