"""把資料集的錄音批次轉成特徵表 features.csv（負責人：#5，給 #3 訓練用）。

每首歌需要一份參考 song.json（用 offline/make_song.py 從原曲產生）。

資料夾結構範例（Acapella）：
    data/datasets/acapella/song1/*.wav   ← 同一首歌、不同歌手的錄音
    data/songs/acapella_song1/song.json  ← 這首歌的參考旋律

用法：
    python scoring/extract_dataset.py --audio-dir data/datasets/acapella/song1 \
        --song acapella_song1 --out data/features/acapella_song1.csv

之後由 #3 把評審分數（labels）依檔名合併進來，再跑 scoring/train.py。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.features import extract_features, flatten  # noqa: E402
from scoring.pitch_utils import detect_pitch, hz_to_midi  # noqa: E402


def wav_to_frames(path, method="pyin"):
    import librosa
    import numpy as np

    y, sr = librosa.load(path, sr=22050, mono=True)
    times, f0, voiced, rms = detect_pitch(y, sr, method=method)
    midi = hz_to_midi(f0)
    return [{"t": float(t), "midi": None if np.isnan(m) else float(m), "voiced": bool(v), "rms": float(r)}
            for t, m, v, r in zip(times, midi, voiced, rms)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio-dir", type=Path, required=True)
    ap.add_argument("--song", required=True, help="data/songs/ 底下的參考歌曲 id")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--method", default="pyin")
    args = ap.parse_args()

    song = json.loads((ROOT / "data" / "songs" / args.song / "song.json").read_text(encoding="utf-8"))
    rows = []
    for wav in sorted(args.audio_dir.glob("*.wav")):
        feats = extract_features(song, wav_to_frames(wav, args.method))
        rows.append({"file": wav.name, "song": args.song, **flatten(feats)})
        print(f"  {wav.name}  音準誤差中位數 {feats['pitch']['median_abs_cents']:.0f} cent")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"完成：{len(rows)} 筆 → {args.out}")


if __name__ == "__main__":
    main()
