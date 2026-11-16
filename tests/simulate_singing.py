"""用 demo 歌曲模擬五種演唱，檢查評分是否「夠嚴格」。

用法：先跑 python offline/make_demo_song.py，再跑 python tests/simulate_singing.py
預期：正常唱分數最高；偏高半音 → 音準掉；拖拍 → 節奏掉；亂唱 → 總分最低。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.features import extract_features  # noqa: E402
from scoring.pitch_utils import detect_pitch, hz_to_midi  # noqa: E402
from scoring.scorer import score  # noqa: E402


def frames_from(times, midi, rms):
    return [{"t": float(t), "midi": (None if np.isnan(m) else float(m)), "voiced": bool(not np.isnan(m)),
             "rms": float(r)} for t, m, r in zip(times, midi, rms)]


def main():
    import librosa

    song_dir = ROOT / "data" / "songs" / "demo"
    song = json.loads((song_dir / "song.json").read_text(encoding="utf-8"))
    y, sr = librosa.load(song_dir / "vocals.wav", sr=22050)
    times, f0, _, rms = detect_pitch(y, sr, method="yin")
    midi = hz_to_midi(f0)
    rng = np.random.default_rng(0)

    random_midi = midi.copy()
    seg = np.repeat(rng.integers(57, 72, size=len(midi) // 25 + 1), 25)[:len(midi)]
    random_midi[~np.isnan(midi)] = seg[~np.isnan(midi)]

    cases = {
        "正常唱": (times, midi),
        "偏高半音": (times, midi + 1.0),
        "拖拍 350ms": (times + 0.35, midi),
        "亂唱": (times, random_midi),
    }
    print(f"{'條件':<10}{'總分':>6}{'音準':>6}{'節奏':>6}{'走向':>6}{'表現':>6}")
    for name, (t, m) in cases.items():
        f = extract_features(song, frames_from(t, m, rms))
        s = score(f)
        print(f"{name:<10}{s['overall']:>6}{s['pitch']:>6}{s['rhythm']:>6}{s['contour']:>6}{s['expression']:>6}"
              f"   {s['tips'][0]}")


if __name__ == "__main__":
    main()
