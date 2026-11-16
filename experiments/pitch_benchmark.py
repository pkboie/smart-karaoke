"""Proposal 承諾的三項實驗（Pitch accuracy、Efficiency、Noise robustness）的起點。

負責人：#6 Pitch accuracy、#2 Efficiency、#1 Noise robustness

做法：拿一首有正確答案（song.json）的歌，比較不同音高偵測方法：
- Pitch accuracy：偵測到的音高 vs. 參考音符，誤差 < 50 cent 的比例
- Efficiency：處理 1 秒音訊要花多少時間
- Noise robustness：把伴奏以不同音量混進人聲，看準確度掉多少

用法：python experiments/pitch_benchmark.py --song demo
（demo 歌曲由 offline/make_demo_song.py 產生；正式實驗請換成你們的歌）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.pitch_utils import HOP_SEC, detect_pitch, fold_cents, hz_to_midi, notes_to_curve  # noqa: E402


def accuracy(song, times, f0):
    ref = notes_to_curve(song["notes"], song["duration"], hop=HOP_SEC)
    n = min(len(ref), len(f0))
    ref, est = ref[:n], hz_to_midi(f0[:n])
    mask = ~np.isnan(ref)
    ok = ~np.isnan(est[mask]) & (np.abs(fold_cents(est[mask] - ref[mask])) < 50)
    return float(np.mean(ok))


def main():
    import librosa

    ap = argparse.ArgumentParser()
    ap.add_argument("--song", default="demo")
    ap.add_argument("--methods", nargs="+", default=["yin", "pyin"])
    ap.add_argument("--snr-db", nargs="+", type=float, default=[None, 20, 10, 5, 0],
                    help="人聲對伴奏的音量比（dB），None = 純人聲")
    args = ap.parse_args()

    d = ROOT / "data" / "songs" / args.song
    song = json.loads((d / "song.json").read_text(encoding="utf-8"))
    vocals, sr = librosa.load(d / "vocals.wav", sr=22050)
    acc, _ = librosa.load(d / "accompaniment.wav", sr=22050)
    n = min(len(vocals), len(acc))
    vocals, acc = vocals[:n], acc[:n]

    print(f"{'方法':<8}{'SNR(dB)':>9}{'準確率':>9}{'每秒耗時(ms)':>14}")
    for method in args.methods:
        for snr in args.snr_db:
            if snr is None:
                y = vocals
            else:
                gain = np.sqrt(np.mean(vocals ** 2) / (np.mean(acc ** 2) * 10 ** (snr / 10)))
                y = vocals + gain * acc
            t0 = time.perf_counter()
            times, f0, _, _ = detect_pitch(y, sr, method=method)
            ms_per_sec = (time.perf_counter() - t0) * 1000 / (n / sr)
            label = "clean" if snr is None else f"{snr:g}"
            print(f"{method:<8}{label:>9}{accuracy(song, times, f0):>9.1%}{ms_per_sec:>14.1f}")


if __name__ == "__main__":
    main()
