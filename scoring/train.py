"""訓練評分模型並和 baseline 比較（負責人：#3）。

輸入：一個 CSV，每列是一次演唱，欄位包含
    song（用來做 leave-one-song-out）、特徵欄位（pitch.* rhythm.* contour.* expression.*）、
    以及目標分數欄位（例如 overall，用 --target 指定）

用法：
    python scoring/train.py data/features/all.csv --target overall
    python scoring/train.py --demo          # 用假資料測試整個流程

輸出：每個模型的 Spearman ρ、MAE；最好的模型存到 models/overall.joblib
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
PITCH_ONLY = ["pitch.hit_rate_100c"]  # baseline：只看音準（模擬一般 KTV）


def models():
    out = {
        "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "RandomForest": RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=0),
    }
    try:
        from xgboost import XGBRegressor
        out["XGBoost"] = XGBRegressor(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8)
    except ImportError:
        pass
    return out


def evaluate(df, feature_cols, target):
    """leave-one-song-out：每次留一首歌完全不看，測試能不能套用到新歌。"""
    X, y, g = df[feature_cols].to_numpy(), df[target].to_numpy(), df["song"].to_numpy()
    results = {}
    candidates = {"Baseline（只看音準）": None, **models()}
    for name, model in candidates.items():
        preds = np.zeros_like(y, dtype=float)
        for tr, te in LeaveOneGroupOut().split(X, y, g):
            if model is None:
                p = make_pipeline(StandardScaler(), Ridge()).fit(df.iloc[tr][PITCH_ONLY], y[tr])
                preds[te] = p.predict(df.iloc[te][PITCH_ONLY])
            else:
                preds[te] = model.fit(X[tr], y[tr]).predict(X[te])
        rho = spearmanr(preds, y).correlation
        mae = float(np.mean(np.abs(preds - y)))
        results[name] = (rho, mae)
        print(f"{name:<22} Spearman ρ = {rho:6.3f}   MAE = {mae:6.3f}")
    return results


def make_demo_data(n_songs=6, n_singers=22, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_songs):
        for k in range(n_singers):
            skill = rng.normal()
            r = {
                "song": f"song{s}",
                "pitch.median_abs_cents": max(5, 60 - 20 * skill + rng.normal(0, 10)),
                "pitch.hit_rate_50c": np.clip(0.6 + 0.15 * skill + rng.normal(0, 0.05), 0, 1),
                "pitch.hit_rate_100c": np.clip(0.8 + 0.1 * skill + rng.normal(0, 0.05), 0, 1),
                "rhythm.median_abs_onset_ms": max(10, 150 - 40 * skill + rng.normal(0, 30)),
                "rhythm.early_rate": np.clip(0.1 - 0.05 * skill + rng.normal(0, 0.03), 0, 1),
                "rhythm.late_rate": np.clip(0.1 - 0.05 * skill + rng.normal(0, 0.03), 0, 1),
                "contour.interval_accuracy": np.clip(0.7 + 0.1 * skill + rng.normal(0, 0.05), 0, 1),
                "contour.note_coverage": np.clip(0.9 + 0.05 * skill, 0, 1),
                "expression.vibrato_cents": max(0, 20 + 8 * skill + rng.normal(0, 5)),
                "expression.dynamics_std": max(0, 0.3 + 0.05 * skill + rng.normal(0, 0.05)),
            }
            r["overall"] = 6 + 1.2 * skill + rng.normal(0, 0.5)
            rows.append(r)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", type=Path)
    ap.add_argument("--target", default="overall")
    ap.add_argument("--demo", action="store_true", help="用假資料測試流程（數字沒有意義）")
    ap.add_argument("--scale", type=float, default=10.0, help="把模型輸出換算成 0–100 分（Acapella 是 0–10 分，所以 ×10）")
    args = ap.parse_args()

    df = make_demo_data() if args.demo else pd.read_csv(args.csv)
    feature_cols = [c for c in df.columns if c.split(".")[0] in {"pitch", "rhythm", "contour", "expression"}]
    print(f"{len(df)} 筆資料、{df['song'].nunique()} 首歌、{len(feature_cols)} 個特徵\n")

    results = evaluate(df, feature_cols, args.target)
    best = max((k for k in results if not k.startswith("Baseline")), key=lambda k: results[k][0])
    model = models()[best].fit(df[feature_cols].to_numpy(), df[args.target].to_numpy())

    if args.demo:
        print(f"\n（demo 模式不存模型）最佳：{best}")
        return
    import joblib
    (ROOT / "models").mkdir(exist_ok=True)
    joblib.dump({"model": model, "columns": feature_cols, "scale": args.scale}, ROOT / "models" / "overall.joblib")
    print(f"\n最佳模型 {best} 已存到 models/overall.joblib，後端會自動改用它預測總分")


if __name__ == "__main__":
    main()
