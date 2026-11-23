"""Proposal 承諾的三項實驗（Pitch accuracy、Efficiency、Noise robustness）的起點。

負責人：#6 Pitch accuracy、#2 Efficiency、#1 Noise robustness

做法：拿有正確答案的人聲，比較不同音高偵測方法：
- Pitch accuracy：偵測到的音高 vs. 參考音高，逐 frame 比對（指標見 compare_to_reference）
- Efficiency：處理 1 秒音訊要花多少時間
- Noise robustness：把伴奏以不同音量混進人聲，看準確度掉多少

資料來源（--dataset）：
- mir1k：MIR-1K 人工音高標註當答案（正式實驗用）。右聲道 = 人聲、左聲道 = 伴奏。
- song ：data/songs/<id>/ 的 song.json 當答案。注意 song.json 若由 pYIN 自動產生，
         pYIN 會自己考自己（循環論證），只能用「手動修正過」的 song.json。

用法：
  python experiments/pitch_benchmark.py --dataset mir1k --limit 10
  python experiments/pitch_benchmark.py --dataset song --song demo
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.pitch_utils import (  # noqa: E402
    HOP_SEC,
    detect_pitch,
    fold_cents,
    hz_to_midi,
    notes_to_curve,
)

MIR1K_DIR = ROOT / "data" / "datasets" / "mir1k" / "MIR-1K"
MIR1K_HOP = 0.02  # .pv 每 20 ms 一筆
MIR1K_FIRST = 0.02  # 第一筆在 20 ms（不是 0）


# ---------- 指標 ----------
def compare_to_reference(ref_midi: np.ndarray, est_midi: np.ndarray) -> dict:
    """逐 frame 比對參考音高與偵測音高，回傳 E1 的各項指標。

    輸入：兩個等長陣列，單位是 MIDI（可以是小數，60.5 = 中央 C 再高 50 cent），
          **NaN 代表該 frame 無聲**（參考：沒在唱；偵測：方法判定沒聲音）。

    需要回傳的指標（PROJECT_PLAN.md 第 5 節 E1）：
      rpa           Raw Pitch Accuracy：在「參考有聲」的 frame 中，偵測音高與參考差 < 50 cent 的比例
      rca           Raw Chroma Accuracy：同上，但忽略八度（提示：fold_cents）
      voicing_recall 參考有聲的 frame 中，偵測也判為有聲的比例
      voicing_fa    參考無聲的 frame 中，偵測卻判為有聲的比例（誤判率）
      mean_abs_cents 兩邊都有聲的 frame 的平均 |cent 誤差|

    沒有任何「參考有聲」frame 時，相關指標回傳 NaN（不要除以 0）。
    """

    def safe_mean(x):
        return x.mean() if len(x) > 0 else np.nan

    # 遮罩：挑出要看的格子
    ref_v = ~np.isnan(ref_midi)  # 標準答案有聲
    est_v = ~np.isnan(est_midi)  # 程式說有聲
    both = ref_v & est_v  # 兩邊都有聲

    # 誤差
    cents = (est_midi - ref_midi) * 100  # 原始誤差（cent）
    folded = fold_cents(est_midi - ref_midi)  # 忽略八度的誤差（cent）

    # 音高正確率（只看歌手有唱的格子；漏掉的格子 NaN < 50 → False，自動算錯）
    rpa = safe_mean((np.abs(cents) < 50)[ref_v])
    rca = safe_mean((np.abs(folded) < 50)[ref_v])

    # 有聲／無聲判斷
    voicing_recall = safe_mean(est_v[ref_v])  # 有唱 → 有聽到
    voicing_fa = safe_mean(est_v[~ref_v])  # 沒唱 → 卻說有聲

    # 聽對時的細微誤差
    mean_abs_cents = safe_mean(np.abs(folded[both]))

    return {
        "rpa": rpa,
        "rca": rca,
        "voicing_recall": voicing_recall,
        "voicing_fa": voicing_fa,
        "mean_abs_cents": mean_abs_cents,
    }


def sample_at(times_ref: np.ndarray, f0_hz: np.ndarray) -> np.ndarray:
    """把偵測結果（每 HOP_SEC 一筆，第 k 筆在 k*HOP_SEC）取樣到參考的時間點，回傳 MIDI（無聲 = NaN）。"""
    idx = np.round(times_ref / HOP_SEC).astype(int)
    est = np.full(len(times_ref), np.nan)
    ok = idx < len(f0_hz)
    est[ok] = hz_to_midi(f0_hz[idx[ok]])
    return est


# ---------- 資料來源：每個 clip 回傳 (名稱, 人聲, 伴奏, sr, 參考時間, 參考 MIDI) ----------
def iter_mir1k(limit: int | None, seed: int):
    import librosa

    wavs = sorted((MIR1K_DIR / "Wavfile").glob("*.wav"))
    if not wavs:
        sys.exit(
            f"找不到 MIR-1K：{MIR1K_DIR}/Wavfile（解壓方式見 docs/git_workflow.md 第 0 節）"
        )
    if limit:
        # 隨機抽（固定 seed 可重現），避免只抽到同一位歌手
        wavs = sorted(random.Random(seed).sample(wavs, min(limit, len(wavs))))
    for wav in wavs:
        y, sr = librosa.load(wav, sr=None, mono=False)  # shape (2, n)
        pv = np.loadtxt(MIR1K_DIR / "PitchLabel" / f"{wav.stem}.pv", ndmin=1)
        ref = np.where(pv > 0, pv, np.nan)
        times = MIR1K_FIRST + np.arange(len(pv)) * MIR1K_HOP
        yield wav.stem, y[1], y[0], sr, times, ref


def iter_song(song_id: str):
    import librosa

    d = ROOT / "data" / "songs" / song_id
    song = json.loads((d / "song.json").read_text(encoding="utf-8"))
    vocals, sr = librosa.load(d / "vocals.wav", sr=22050)
    acc, _ = librosa.load(d / "accompaniment.wav", sr=22050)
    ref = notes_to_curve(song["notes"], song["duration"], hop=HOP_SEC)
    times = np.arange(len(ref)) * HOP_SEC
    yield song_id, vocals, acc, sr, times, ref


def mix(vocals, acc, snr):
    """snr=None → 純人聲；否則以 snr dB（人聲對伴奏）混入伴奏。"""
    n = min(len(vocals), len(acc))
    vocals, acc = vocals[:n], acc[:n]
    if snr is None:
        return vocals
    gain = np.sqrt(np.mean(vocals**2) / (np.mean(acc**2) * 10 ** (snr / 10) + 1e-12))
    return vocals + gain * acc


# ---------- 主程式 ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["mir1k", "song"], default="mir1k")
    ap.add_argument("--song", default="demo", help="--dataset song 時用哪首")
    ap.add_argument(
        "--limit", type=int, default=10, help="MIR-1K 抽幾段（0 = 全部 1000 段）"
    )
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--methods", nargs="+", default=["yin", "pyin"])
    ap.add_argument(
        "--snr-db",
        nargs="+",
        default=["clean"],
        help="人聲對伴奏的音量比（dB），clean = 純人聲。例：clean 20 10 5 0 -5",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "experiments" / "results" / "pitch_benchmark.csv",
    )
    args = ap.parse_args()
    snrs = [None if s == "clean" else float(s) for s in args.snr_db]

    clips = (
        list(iter_mir1k(args.limit or None, args.seed))
        if args.dataset == "mir1k"
        else list(iter_song(args.song))
    )
    print(f"{args.dataset}：{len(clips)} 段")

    rows = []
    for name, vocals, acc, sr, times, ref in clips:
        for method in args.methods:
            for snr in snrs:
                y = mix(vocals, acc, snr)
                t0 = time.perf_counter()
                _, f0, _, _ = detect_pitch(y, sr, method=method)
                ms_per_sec = (time.perf_counter() - t0) * 1000 / (len(y) / sr)
                m = compare_to_reference(ref, sample_at(times, f0))
                rows.append(
                    {
                        "clip": name,
                        "method": method,
                        "snr_db": "clean" if snr is None else f"{snr:g}",
                        "ms_per_sec": round(ms_per_sec, 2),
                        **{k: round(float(v), 4) for k, v in m.items()},
                    }
                )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # 摘要：每個方法 × SNR 的平均
    import pandas as pd

    df = pd.DataFrame(rows)
    print(
        df.drop(columns="clip")
        .groupby(["method", "snr_db"], sort=False)
        .mean()
        .round(3)
        .to_string()
    )
    print(f"\n逐段結果：{args.out}")


if __name__ == "__main__":
    main()
