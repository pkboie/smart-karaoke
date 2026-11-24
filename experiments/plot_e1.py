"""E1 圖：rpa 與 voicing_fa 隨 SNR 的變化（YIN / pYIN / pitchy）。

用法：
    python experiments/plot_e1.py                                   # 預設讀 e1_mir1k_100_snr.csv
    python experiments/plot_e1.py --csv <檔案> --out <圖檔.png>

輸入是 pitch_benchmark.py 的輸出：每一列 = 一段 × 一種方法 × 一種 SNR。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")  # 不開視窗，直接存檔（WSL 沒有螢幕也能跑）
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "experiments" / "results"

# x 軸順序：由乾淨到吵。snr_db 欄位裡 "clean" 和數字混在一起，所以一律當字串處理
SNR_ORDER = ["clean", "20", "10", "5", "0", "-5"]
SNR_LABELS = ["clean", "20", "10", "5", "0", "−5"]

# 顏色跟著方法走，不跟著排名走（三色已通過色盲檢查）；marker 形狀是第二種辨識方式
STYLE = {
    "yin": {"label": "YIN", "color": "#2a78d6", "marker": "o"},
    "pyin": {"label": "pYIN", "color": "#eb6834", "marker": "s"},
    "pitchy": {"label": "pitchy (McLeod)", "color": "#1baf7a", "marker": "^"},
}

INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"


def summarize(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """把每段的結果彙整成每個 (method, snr_db) 一列。

    回傳的 DataFrame：
      - index：MultiIndex (method, snr_db)
      - 欄位：mean（平均）、ci95（95% 信賴區間的半寬）

    ci95 = 1.96 × 標準差 ÷ √n，n 是該組的段數。
    某一段的 metric 若是 NaN（例如那段沒有無聲格，voicing_fa 算不出來），
    不要算進平均，也不要算進 n。
    """
    s = df.groupby(["method", "snr_db"])[metric].agg(["mean", "std", "count"])
    s["ci95"] = 1.96 * s["std"] / np.sqrt(s["count"])
    return s[["mean", "ci95"]]


def plot_metric(ax, summary: pd.DataFrame, title: str, ylabel: str, band: bool) -> None:
    x = np.arange(len(SNR_ORDER))
    for method, st in STYLE.items():
        if method not in summary.index.get_level_values("method"):
            continue
        s = summary.loc[method].reindex(SNR_ORDER)
        ax.plot(
            x,
            s["mean"],
            color=st["color"],
            marker=st["marker"],
            markersize=7,
            linewidth=2,
            label=st["label"],
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            zorder=3,
        )
        if band:
            ax.fill_between(
                x,
                s["mean"] - s["ci95"],
                s["mean"] + s["ci95"],
                color=st["color"],
                alpha=0.15,
                linewidth=0,
                zorder=2,
            )

    ax.set_title(title, loc="left", fontsize=12, color=INK, fontweight="bold")
    ax.set_xticks(x, SNR_LABELS)
    ax.set_xlabel(
        "Accompaniment SNR (dB)   cleaner → noisier", color=INK_2, fontsize=9.5
    )
    ax.set_ylabel(ylabel, color=INK_2, fontsize=9.5)
    ax.set_ylim(0, 1.02)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)


def label_line_ends(ax, summary: pd.DataFrame) -> None:
    """在最右端（−5 dB）直接標方法名，讓讀者不用回頭看圖例。"""
    last = len(SNR_ORDER) - 1
    for method, st in STYLE.items():
        if method not in summary.index.get_level_values("method"):
            continue
        y = summary.loc[(method, SNR_ORDER[-1]), "mean"]
        ax.annotate(
            st["label"],
            (last, y),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=INK,
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=RESULTS / "e1_mir1k_100_snr.csv")
    ap.add_argument("--out", type=Path, default=RESULTS / "e1_snr.png")
    args = ap.parse_args()

    df = pd.read_csv(args.csv, dtype={"snr_db": str})
    n_clips = df["clip"].nunique()

    rpa = summarize(df, "rpa")
    fa = summarize(df, "voicing_fa")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2), facecolor=SURFACE)
    for ax in (ax1, ax2):
        ax.set_facecolor(SURFACE)

    plot_metric(
        ax1, rpa, "Raw pitch accuracy (higher is better)", "RPA (±50 cent)", band=True
    )
    plot_metric(
        ax2, fa, "Voicing false alarm (lower is better)", "False-alarm rate", band=False
    )
    label_line_ends(ax2, fa)
    ax2.set_xlim(-0.3, len(SNR_ORDER) - 1 + 0.9)  # 右邊留位置給直接標籤

    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=3, frameon=False, fontsize=9.5)
    fig.suptitle(
        f"E1 · Pitch tracking under accompaniment  (MIR-1K, {n_clips} clips, shaded = 95% CI)",
        x=0.01,
        ha="left",
        fontsize=10,
        color=INK_2,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=200, facecolor=SURFACE)
    print(f"已輸出 {args.out}")
    print(
        pd.concat({"rpa": rpa["mean"], "voicing_fa": fa["mean"]}, axis=1)
        .unstack("method")
        .reindex(SNR_ORDER)
        .round(3)
    )


if __name__ == "__main__":
    main()
