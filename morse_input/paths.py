"""Project resources and default storage, independent of the working directory."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMING_CONFIG = ROOT / "config" / "config.json"
HAND_MODEL = ROOT / "assets" / "hand_landmarker.task"
PERSONAL_DATA = ROOT / "personal-data"
RESULTS = ROOT / "results"
