"""檢查 experiments/pitch_benchmark.py 的 compare_to_reference()。

用法：python tests/check_pitch_metrics.py

5 格小資料涵蓋所有情況：
  格 0：唱對（差 30 cent）  格 1：八度錯誤（高 1200 cent）  格 2：漏掉（偵測無聲）
  格 3：誤判（沒唱卻說有聲）格 4：正確判為無聲
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.pitch_benchmark import compare_to_reference  # noqa: E402

nan = np.nan
ref = np.array([60, 60, 62, nan, nan])
est = np.array([60.3, 72, nan, 64, nan])

EXPECTED = {
    "rpa": 1 / 3,
    "rca": 2 / 3,
    "voicing_recall": 2 / 3,
    "voicing_fa": 1 / 2,
    "mean_abs_cents": 15.0,
}

m = compare_to_reference(ref, est)
ok_all = True
for key, want in EXPECTED.items():
    if key not in m:
        print(f"  ⏳ {key:<15} 還沒寫")
        ok_all = False
        continue
    got = float(m[key])
    ok = np.isclose(got, want)
    ok_all &= ok
    print(f"  {'✅' if ok else '❌'} {key:<15} 得到 {got:.3f}，應該是 {want:.3f}")

# 邊界情況：整段都沒唱 → 跟「參考有聲」有關的指標要是 NaN，而且不能當掉
silent = compare_to_reference(np.array([nan, nan]), np.array([60.0, nan]))
edge_ok = all(np.isnan(silent.get(k, 0)) for k in ("rpa", "rca", "voicing_recall", "mean_abs_cents"))
print(f"  {'✅' if edge_ok else '❌'} 整段沒唱時回傳 NaN")

print("\n全部通過！" if ok_all and edge_ok else "\n還沒全對，繼續加油")
