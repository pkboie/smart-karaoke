"""檢查 experiments/plot_e1.py 的 summarize()：用可以手算的小資料對答案。

    python tests/check_plot_summary.py
"""
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from plot_e1 import summarize  # noqa: E402

df = pd.DataFrame({
    "clip":   ["a", "b", "c", "a", "b", "c"],
    "method": ["yin", "yin", "yin", "pyin", "pyin", "pyin"],
    "snr_db": ["clean"] * 6,
    "rpa":    [0.9, 0.8, 0.7, 1.0, 1.0, float("nan")],
})

s = summarize(df, "rpa")
ok = True

def check(name, got, want):
    global ok
    good = math.isclose(got, want, abs_tol=1e-6)
    ok &= good
    print(f"{'✓' if good else '✗'} {name}: 得到 {got:.6f}，應為 {want:.6f}")

# yin：平均 0.8；樣本標準差 0.1；n = 3 → 1.96 × 0.1 / √3
check("yin mean", s.loc[("yin", "clean"), "mean"], 0.8)
check("yin ci95", s.loc[("yin", "clean"), "ci95"], 1.96 * 0.1 / math.sqrt(3))
# pyin：NaN 不算 → 只有 2 段，都是 1.0 → 平均 1.0、標準差 0、ci95 0
check("pyin mean（NaN 要跳過）", s.loc[("pyin", "clean"), "mean"], 1.0)
check("pyin ci95（n 只算 2）", s.loc[("pyin", "clean"), "ci95"], 0.0)

print("\n全部通過" if ok else "\n有錯，再看看")
sys.exit(0 if ok else 1)
