"""Calibration and per-frame observations in palm-width units."""
from math import dist
from statistics import median


def measure(points, width, height):
    def pixels(i):
        return points[i].x * width, points[i].y * height

    palm = dist(pixels(5), pixels(17))
    if palm < 1:
        return None
    return tuple(dist(pixels(4), pixels(i)) / palm for i in (8, 12))


def calibrate(samples):
    opened, index, middle = samples
    limits = []
    for i, (pinch, other, name) in enumerate(((index, middle, "cái–trỏ"),
                                               (middle, index, "cái–giữa"))):
        closed = [pair[i] for pair in pinch]
        released = [pair[i] for pair in opened + other]
        if max(closed) >= min(released):
            raise ValueError(f"Mẫu {name} chồng lấn. Chỉnh góc tay và hiệu chuẩn lại.")
        low = median(closed)
        step = (median(released) - low) / 3
        limits.append((low + step, low + 2 * step))
    return limits


def classify(pair, limits):
    if pair is None:
        return "unknown"
    index, middle = pair
    (ic, io), (mc, mo) = limits
    if index <= ic and middle <= mc:
        return "unknown"
    if index >= io and middle >= mo:
        return "open"
    if index <= ic and middle >= mo:
        return "dot"
    if middle <= mc and index >= io:
        return "dash"
    return "transition"
