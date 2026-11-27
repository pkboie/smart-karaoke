"""檢查 experiments/plot_e1.py 的 paired_diff()：用可以手算的小資料對答案。

    python tests/check_paired_diff.py
"""
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from plot_e1 import paired_diff  # noqa: E402

nan = float("nan")
df = pd.DataFrame({
    "clip":   ["a", "b", "c", "d",   "a", "b", "c", "d",   "a", "a"],
    "method": ["new"] * 4 + ["old"] * 4 + ["new", "old"],
    "snr_db": ["clean"] * 8 + ["10", "10"],
    "rpa":    [0.9, 0.8, 0.7, nan,   0.8, 0.8, 0.5, 0.6,   0.1, 0.9],
})
# clean：a 0.9−0.8 = 0.1、b 0.8−0.8 = 0、c 0.7−0.5 = 0.2、d 有 NaN → 不算
# 差值 [0.1, 0, 0.2] → 平均 0.1、樣本標準差 0.1、n = 3
# 10 dB 那兩列（差值 −0.8）不能混進來

r = paired_diff(df, "new", "old", "clean")
ok = True


def check(name, got, want):
    global ok
    good = math.isclose(float(got), want, abs_tol=1e-6)
    ok &= good
    print(f"{'✓' if good else '✗'} {name}: 得到 {float(got):.6f}，應為 {want:.6f}")


check("mean（只看 clean、NaN 段跳過）", r["mean"], 0.1)
check("ci95", r["ci95"], 1.96 * 0.1 / math.sqrt(3))
check("n（d 段不算）", r["n"], 3)
check("a_better（差值 > 0）", r["a_better"], 2)
check("b_better（差值 = 0 的 b 段不算）", r["b_better"], 0)

r10 = paired_diff(df, "new", "old", "10")
check("10 dB 只有 a 段：mean", r10["mean"], -0.8)
check("10 dB：b_better", r10["b_better"], 1)

print("\n全部通過" if ok else "\n有錯，再看看")
sys.exit(0 if ok else 1)
