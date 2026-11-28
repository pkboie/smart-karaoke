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
import subprocess
import sys
import time
import psutil
import threading
import tracemalloc
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


PITCHY_SR = 48000  # 瀏覽器麥克風常見的取樣率；前端一次分析 2048 個樣本 ≈ 43 ms


def detect_pitchy(y: np.ndarray, sr: int) -> np.ndarray:
    """用 Node 跑前端的 pitchy（experiments/pitchy_f0.mjs），回傳每 HOP_SEC 一筆的 f0（Hz，無聲 = NaN）。

    先重新取樣到 48 kHz：前端固定用 2048 個樣本的視窗，同樣 2048 個樣本在 16 kHz 是 128 ms，
    會和 demo 時的實際行為（約 43 ms）差很多。
    """
    import librosa

    y48 = librosa.resample(y, orig_sr=sr, target_sr=PITCHY_SR).astype("<f4")
    out = subprocess.run(["node", str(ROOT / "experiments" / "pitchy_f0.mjs"), str(PITCHY_SR)],
                         input=y48.tobytes(), capture_output=True, check=True)
    res = json.loads(out.stdout)
    assert abs(res["hop_sec"] - HOP_SEC) < 1e-9
    return np.array([np.nan if v is None else v for v in res["f0"]], dtype=float)


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


# ---------- E2 記憶體量測（僅 --profile-memory 時啟用） ----------
def measure_peak_memory(run_detector):
    """執行偵測時定期量測 Python + 子程序 RSS，以及 Python allocations 的峰值。

    peak_rss_mb: 所有觀測到的程序 RSS 相加之取樣峰值（包含 Python 基礎用量）。
    python_alloc_peak_mb: tracemalloc 的 Python allocations 峰值，不含 NumPy/native/Node 分配。
    取樣間隔 5 ms；很短的子程序或尖峰仍可能漏掉。
    """
    process = psutil.Process()
    stop_event = threading.Event()
    ready_event = threading.Event()
    peak_rss = 0

    def sample_rss():
        nonlocal peak_rss
        try:
            processes = [process] + process.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            processes = [process]
        total_rss = 0
        for p in processes:
            try:
                total_rss += p.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        peak_rss = max(peak_rss, total_rss)

    def monitor():
        sample_rss()  # 確保即使演算法很快，也有基準值
        ready_event.set()
        while not stop_event.wait(0.005):
            sample_rss()

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    ready_event.wait()
    tracemalloc.start()
    try:
        result = run_detector()
        _, python_peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        stop_event.set()
        thread.join()
        sample_rss()

    return result, peak_rss / (1024 ** 2), python_peak / (1024 ** 2)


# ---------- 主程式 ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["mir1k", "song"], default="mir1k")
    ap.add_argument("--song", default="demo", help="--dataset song 時用哪首")
    ap.add_argument(
        "--limit", type=int, default=10, help="MIR-1K 抽幾段（0 = 全部 1000 段）"
    )
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--profile-memory", action="store_true",
                    help="E2：記錄 Python+子程序 peak RSS 和 tracemalloc 記憶體")
    ap.add_argument("--methods", nargs="+", default=["yin", "pyin"],
                    help="yin、pyin、crepe（需 torchcrepe）、pitchy（需 node）")
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
                # 同一份偵測程式可選擇是否開啟記憶體 profiling。
                # pitchy 的 Node 子程序也會在 RSS 取樣範圍內。
                if method == "pitchy":
                    run_detector = lambda: detect_pitchy(y, sr)
                else:
                    run_detector = lambda: detect_pitch(y, sr, method=method)[1]

                t0 = time.perf_counter()
                if args.profile_memory:
                    f0, peak_rss_mb, python_alloc_peak_mb = measure_peak_memory(run_detector)
                else:
                    f0 = run_detector()
                ms_per_sec = (time.perf_counter() - t0) * 1000 / (len(y) / sr)
                m = compare_to_reference(ref, sample_at(times, f0))

                row = {
                    "clip": name,
                    "method": method,
                    "snr_db": "clean" if snr is None else f"{snr:g}",
                    "ms_per_sec": round(ms_per_sec, 2),
                }
                if args.profile_memory:
                    row["peak_rss_mb"] = round(peak_rss_mb, 2)
                    row["python_alloc_peak_mb"] = round(python_alloc_peak_mb, 2)
                row.update({k: round(float(v), 4) for k, v in m.items()})
                rows.append(row)

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
