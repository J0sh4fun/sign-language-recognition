"""Guided recording of confirmed poses, blind validation and paired webcam trials."""
import tkinter as tk
from tkinter import ttk, messagebox
import time

from .app import App, run_camera
from .experiment import fingerprint, fit, read, records, save, schedule, trial_path
from .gesture import calibrate
from .morse import Decoder, Timing
from .personal import GAP_MS, MODEL, Model, features

NAMES = {"open": "Tách cả hai cặp ngón", "dot": "Chụm cái–trỏ", "dash": "Chụm cái–giữa",
         "both": "Chụm đồng thời cả hai cặp"}


class Recorder(App):
    def __init__(self, root, camera, tracker, timing, model, base, session, launch, digest):
        super().__init__(root, camera, tracker, timing, model)
        self.action.grid_remove()
        self.base, self.session, self.launch, self.digest = base, session, launch, digest
        self.tasks = schedule(session)
        self.index = 0
        while trial_path(base, session, self.index).exists():
            self.index += 1
        self.calibration = []
        self.startup_first = None
        self.controls_ok = None
        self.phase = "idle"
        self.frames = []
        self.last_sample = None
        self.caption = tk.StringVar()
        ttk.Label(root, textvariable=self.caption, wraplength=790).pack()
        controls = ttk.Frame(root)
        controls.pack(pady=4)
        self.next = ttk.Button(controls, command=self.advance)
        self.next.pack(side="left")
        self.retry = ttk.Button(controls, text="Thu lại", command=self.repeat)
        self.retry.pack(side="left")
        for button in (self.next, self.retry):
            button.bind("<space>", self.on_key)
        self.root.title(f"Morse cá nhân · Phiên {session}")
        self.show_task()

    @property
    def task(self):
        return self.tasks[self.index]

    def show_task(self):
        kind, label = self.task
        self.phase = "idle"
        self.decoder = Decoder(self.decoder.timing)
        self.code.set("")
        self.text.set("")
        self.bar["value"] = 0
        self.caption.set(f"Lượt {self.index+1}/{len(self.tasks)} · {NAMES.get(label, label)}")
        self.next.config(text="Bắt đầu", state="normal")
        self.retry.config(state="disabled")
        self.status.set("Thả tay rồi nhấn Bắt đầu khi sẵn sàng.")
        if kind == "phrase":
            self.status.set("Có thể làm quen và sửa bằng Space/Backspace. Bắt đầu sẽ xóa phần thử.")
            if self.session >= 4 and self.index == 0:
                self.caption.set("Làm quen · Giữ một dấu, thử mất tay và chụm cả hai cặp. "
                                 "Kiểm tra Space và Backspace, rồi bấm Bắt đầu.")

    def on_key(self, event):
        if self.task[0] == "phrase":
            if self.phase == "idle":
                self.decoder.backspace()
            elif self.session >= 4 and self.phase == "collect":
                self.delete_after_frames.append(len(self.frames))
                self.decoder.backspace()
        return "break"

    def repeat(self):
        self.frames = []
        self.show_task()

    def advance(self):
        kind, label = self.task
        if self.phase == "idle":
            self.delete_after_frames = []
            if self.session >= 4 and self.index == 0:
                self.controls_ok = messagebox.askyesno(
                    "Kiểm tra thao tác", "Giữ lâu chỉ ghi một dấu, mất tay/chụm cả hai cặp không "
                    "sinh dấu, Space và Backspace đều sửa được trong lượt làm quen?")
            self.frames = []
            self.last_sample = None
            self.start_ms = time.monotonic_ns() // 1_000_000
            self.decoder = Decoder(self.decoder.timing)
            self.phase = "collect"
            if kind == "phrase":
                self.next.config(text="Kết thúc lượt")
            else:
                self.next.config(state="disabled")
            if self.session < 4 or kind != "phrase":
                self.retry.config(state="normal")
            return
        if self.phase == "collect" and kind == "phrase":
            if not self.frames:
                return
            if self.decoder.code and not self.decoder.error:
                self.caption.set("Còn dấu chưa chốt. Tách ngón rồi bấm Kết thúc lượt lần nữa.")
                return
            self.phase = "review"
        if self.phase != "review":
            return
        r = dict(session=self.session, trial=self.index+1, kind=kind, label=label, frames=self.frames)
        if self.session >= 4:
            r["model_sha256"] = self.digest
        if kind == "phrase":
            if self.delete_after_frames:
                r["delete_after_frames"] = self.delete_after_frames
            r.update(live_text=self.decoder.text, live_pending=self.decoder.code,
                     startup_first_ms=self.startup_first)
            if self.session >= 4 and self.index == 0:
                r["controls_ok"] = self.controls_ok
        try:
            if kind == "calibration":
                self.calibration.append(r)
                if len(self.calibration) == 3:
                    try:
                        calibrate([[features(p)[:2] for _, p in row["frames"]] for row in self.calibration])
                    except ValueError as exc:
                        messagebox.showinfo("Thu lại ba tư thế đối chứng", str(exc))
                        self.calibration.clear()
                        self.index = 6
                        self.show_task()
                        return
                    save(trial_path(self.base, self.session, 0).parent / "calibration.json", self.calibration)
            else:
                save(trial_path(self.base, self.session, self.index), r)
        except OSError as exc:
            messagebox.showerror("Không lưu được lượt", str(exc))
            self.root.destroy()
            return
        self.index += 1
        if self.index == len(self.tasks):
            messagebox.showinfo("Hoàn tất", f"Đã lưu phiên {self.session}.")
            self.root.destroy()
        else:
            self.show_task()

    def process_frame(self, points, now):
        kind, label = self.task
        if kind == "phrase" and self.phase in ("idle", "collect"):
            events = super().process_frame(points, now)
            if self.startup_first is None and any(e in ("dot", "dash") for e in events):
                self.startup_first = now - self.launch
            if self.phase == "collect":
                self.frames.append([now-self.start_ms, points])
                self.caption.set(f"Nhập {label} · Chờ chốt chữ cuối rồi bấm Kết thúc lượt.")
            return
        if self.phase != "collect":
            return
        elapsed = now - self.start_ms
        interrupted = self.last_sample is not None and now - self.last_sample > GAP_MS
        self.last_sample = now
        if features(points) is None or interrupted:
            self.frames.clear()
            self.start_ms = now
            self.status.set("Đặt tay vào khung và giữ yên để thu đủ thời gian.")
            return
        if elapsed < 1000:
            self.status.set(f"Đặt tay · {NAMES[label]} · {(1000-elapsed)/1000:.1f} s")
            return
        self.frames.append([elapsed, points])
        self.status.set(f"Giữ yên · {(elapsed-self.frames[0][0])/1000:.1f}/1 s")
        if elapsed-self.frames[0][0] >= 1000:
            self.phase = "review"
            self.status.set("Thả tay. Xác nhận đúng tư thế hoặc chọn Thu lại.")
            self.next.config(text="Đã thả tay · Xác nhận", state="normal")


def start(base, session, camera, timing, launch):
    path = trial_path(base, session, 0).parent
    if session >= 4 and (path / "calibration.json").exists():
        raise ValueError("Phiên này đã hoàn tất.")
    if session <= 3 and trial_path(base, session, len(schedule(session))-1).exists():
        raise ValueError("Phiên này đã hoàn tất.")
    model = digest = None
    if session == 3:
        model = Model(fit(r for s in (1, 2) for r in records(base, s)))
    if session >= 4:
        model = Model.load(base / MODEL)
        digest = fingerprint(base / MODEL)
        timing = Timing(**read(base / MODEL)["timing"])
        if session == 5:
            list(records(base, 4))
        for p in path.glob("*.json"):
            if read(p)["model_sha256"] != digest:
                raise ValueError("Mô hình đã thay đổi giữa phiên.")
    run_camera(camera, lambda root, cam, tracker: Recorder(
        root, cam, tracker, timing, model, base, session, launch, digest))
