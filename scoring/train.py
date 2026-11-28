"""訓練評分模型並和 baseline 比較（負責人：#3）。

輸入：一個 CSV，每列是一次演唱，欄位包含
    song（用來做 leave-one-song-out）、特徵欄位（pitch.* rhythm.* contour.* expression.*）、
    以及目標分數欄位（例如 overall，用 --target 指定）

用法：
    python scoring/train.py data/features/all.csv --target overall
    python scoring/train.py data/features/all.csv --target pitch
    python scoring/train.py data/features/all.csv --target overall --drop-group pitch
    python scoring/train.py --demo --plot          # 用假資料測試流程並輸出圖表

輸出：每個模型的 Spearman ρ（合併 & 每首歌平均）、MAE、95% CI；
      結果存到 experiments/results/；最佳模型存到 models/<target>.joblib
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "experiments" / "results"
PITCH_ONLY = ["pitch.hit_rate_100c"]  # baseline：只看音準（模擬一般 KTV）


def models():
    out = {
        "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "RandomForest": RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=0),
    }
    try:
        from xgboost import XGBRegressor
        out["XGBoost"] = XGBRegressor(
            n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=0
        )
    except ImportError:
        pass
    return out


def _safe_spearman(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3 or np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return float("nan")
    return float(spearmanr(x, y).correlation)


def _bootstrap_ci(preds: np.ndarray, y: np.ndarray, n_boot: int = 1000, seed: int = 42):
    rng = np.random.default_rng(seed)
    n = len(y)
    rhos, maes = [], []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        r = _safe_spearman(preds[idx], y[idx])
        if not np.isnan(r):
            rhos.append(r)
        maes.append(float(np.mean(np.abs(preds[idx] - y[idx]))))
    rho_ci = tuple(np.percentile(rhos, [2.5, 97.5])) if rhos else (float("nan"), float("nan"))
    mae_ci = tuple(np.percentile(maes, [2.5, 97.5]))
    return rho_ci, mae_ci


def evaluate(df: pd.DataFrame, feature_cols: list[str], target_col: str):
    """leave-one-song-out：每次留一首歌完全不看，測試能不能套用到新歌。"""
    X = df[feature_cols].to_numpy()
    y = df[target_col].to_numpy()
    g = df["song"].to_numpy()

    candidates = {
        "Baseline (Mean)": "mean",
        "Baseline (Pitch-only)": "pitch",
        **models(),
    }

    records = []
    oof_preds = {}

    header = f"{'模型':<24} {'合併 ρ (95% CI)':<24} {'每首平均 ρ':<12} {'MAE (95% CI)':<22}"
    print(header)
    print("-" * len(header))

    for name, model in candidates.items():
        preds = np.zeros_like(y, dtype=float)
        song_rhos = []

        for tr, te in LeaveOneGroupOut().split(X, y, g):
            if model == "mean":
                preds[te] = float(np.mean(y[tr]))
            elif model == "pitch":
                p = make_pipeline(StandardScaler(), Ridge()).fit(df.iloc[tr][PITCH_ONLY], y[tr])
                preds[te] = p.predict(df.iloc[te][PITCH_ONLY])
            else:
                preds[te] = model.fit(X[tr], y[tr]).predict(X[te])

            song_rhos.append(_safe_spearman(preds[te], y[te]))

        pooled_rho = _safe_spearman(preds, y)
        per_song_rho = float(np.nanmean(song_rhos)) if not np.all(np.isnan(song_rhos)) else float("nan")
        mae = float(np.mean(np.abs(preds - y)))
        rho_ci, mae_ci = _bootstrap_ci(preds, y)

        oof_preds[name] = preds
        records.append({
            "model": name,
            "pooled_rho": round(pooled_rho, 4),
            "rho_ci_low": round(rho_ci[0], 4),
            "rho_ci_high": round(rho_ci[1], 4),
            "per_song_rho": round(per_song_rho, 4),
            "mae": round(mae, 4),
            "mae_ci_low": round(mae_ci[0], 4),
            "mae_ci_high": round(mae_ci[1], 4),
        })

        rho_str = f"{pooled_rho:6.3f} [{rho_ci[0]:.2f}, {rho_ci[1]:.2f}]"
        song_str = f"{per_song_rho:6.3f}" if not np.isnan(per_song_rho) else "   N/A"
        mae_str = f"{mae:6.3f} [{mae_ci[0]:.2f}, {mae_ci[1]:.2f}]"
        print(f"{name:<24} {rho_str:<24} {song_str:<12} {mae_str:<22}")

    return pd.DataFrame(records), oof_preds


def save_plots(res_df: pd.DataFrame, oof_preds: dict[str, np.ndarray], df: pd.DataFrame, target_col: str, tag: str):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 圖 1：各模型 Spearman ρ 長條圖（含 95% 信賴區間誤差線）
    fig, ax = plt.subplots(figsize=(8, 4.8))
    x = np.arange(len(res_df))
    rhos = res_df["pooled_rho"].to_numpy()
    yerr_low = np.maximum(0, rhos - res_df["rho_ci_low"].to_numpy())
    yerr_high = np.maximum(0, res_df["rho_ci_high"].to_numpy() - rhos)

    colors = ["#95A5A6" if m.startswith("Baseline") else "#4C72B0" for m in res_df["model"]]
    bars = ax.bar(x, rhos, yerr=[yerr_low, yerr_high], capsize=5, color=colors, edgecolor="black", alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(res_df["model"], rotation=15, ha="right")
    ax.set_ylabel("Pooled Spearman ρ (LOSO)")
    ax.set_title(f"Model Comparison — Target: {tag} (with 95% Bootstrap CI)", fontweight="bold")
    ax.set_ylim(min(0, float(np.nanmin(rhos)) - 0.1), 1.05)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    for bar, r in zip(bars, rhos):
        if not np.isnan(r):
            ax.text(bar.get_x() + bar.get_width() / 2, r + 0.03, f"{r:.3f}", ha="center", va="bottom", fontsize=9)

    plt.tight_layout()
    bar_path = RESULTS_DIR / f"e4_{tag}_rho_bar.png"
    plt.savefig(bar_path, dpi=150)
    plt.close()

    # 圖 2：最佳非 Baseline 模型的「預測 vs. 人類評分」散佈圖（依歌曲著色）
    ml_rows = res_df[~res_df["model"].str.startswith("Baseline")]
    best_name = ml_rows.loc[ml_rows["pooled_rho"].idxmax(), "model"]
    best_preds = oof_preds[best_name]
    y_true = df[target_col].to_numpy()

    fig, ax = plt.subplots(figsize=(6, 6))
    for song_name, grp in df.groupby("song"):
        idx = grp.index.to_numpy()
        ax.scatter(y_true[idx], best_preds[idx], label=song_name, alpha=0.75, s=40)

    lo = min(y_true.min(), best_preds.min()) - 0.3
    hi = max(y_true.max(), best_preds.max()) + 0.3
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=1.2, label="Ideal (y = x)")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Human Score")
    ax.set_ylabel(f"Predicted Score ({best_name})")
    ax.set_title(f"Predicted vs. Human — {tag} ({best_name})", fontweight="bold")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    scatter_path = RESULTS_DIR / f"e4_{tag}_scatter.png"
    plt.savefig(scatter_path, dpi=150)
    plt.close()

    print(f"圖表已輸出至：\n- {bar_path}\n- {scatter_path}")


def make_demo_data(n_songs=6, n_singers=22, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_songs):
        for _ in range(n_singers):
            skill = rng.normal()
            r = {
                "song": f"song{s + 1}",
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
            r["overall"] = float(np.clip(5 + 2.0 * skill + rng.normal(0, 0.5), 1, 10))
            r["pitch"] = float(np.clip(5.2 + 2.1 * skill + rng.normal(0, 0.5), 1, 10))
            r["rhythm"] = float(np.clip(5.1 + 1.9 * skill + rng.normal(0, 0.5), 1, 10))
            r["expression"] = float(np.clip(4.0 + 1.8 * skill + rng.normal(0, 0.6), 1, 10))
            rows.append(r)
    return pd.DataFrame(rows)


def resolve_target_column(df: pd.DataFrame, target: str) -> str:
    """自動對應 labels.csv 與模型目標名稱。"""
    if target in df.columns:
        return target
    if target == "overall" and "overall_performance" in df.columns:
        return "overall_performance"
    if target == "expression" and {"vibrato", "dynamic"}.issubset(df.columns):
        df["expression"] = (df["vibrato"] + df["dynamic"]) / 2.0
        return "expression"
    raise KeyError(f"找不到目標欄位 '{target}'，目前 CSV 欄位有：{list(df.columns)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", type=Path)
    ap.add_argument("--target", default="overall", choices=["overall", "pitch", "rhythm", "expression"])
    ap.add_argument("--drop-group", nargs="*", default=[], help="排除指定特徵群組（pitch / rhythm / contour / expression）")
    ap.add_argument("--demo", action="store_true", help="用假資料測試流程（數字沒有意義）")
    ap.add_argument("--plot", action="store_true", help="輸出 ρ 長條圖與預測散佈圖至 experiments/results/")
    ap.add_argument("--scale", type=float, default=10.0, help="把模型輸出換算成 0–100 分（Acapella 是 0–10 分，所以 ×10）")
    ap.add_argument("--prefix", default="", help="輸出檔名前綴（例如 v2_），避免覆蓋既有實驗結果")
    ap.add_argument("--no-save-model", action="store_true", help="只輸出評估與圖表，不覆寫 models/*.joblib")
    args = ap.parse_args()

    if not args.demo and args.csv is None:
        ap.error("請提供特徵 CSV 路徑，或加上 --demo 執行示範測試")

    df = make_demo_data() if args.demo else pd.read_csv(args.csv)
    target_col = resolve_target_column(df, args.target)

    valid_groups = {"pitch", "rhythm", "contour", "expression"} - set(args.drop_group)
    feature_cols = [
        c for c in df.columns
        if "." in c and c.split(".", 1)[0] in valid_groups
    ]

    drop_suffix = f"_drop_{'_'.join(args.drop_group)}" if args.drop_group else ""
    tag = f"{args.prefix}{args.target}{drop_suffix}"

    print(f"目標：{args.target}（欄位：{target_col}）| 排除群組：{args.drop_group or '無'}")
    print(f"{len(df)} 筆資料、{df['song'].nunique()} 首歌、{len(feature_cols)} 個特徵\n")

    res_df, oof_preds = evaluate(df, feature_cols, target_col)

    ml_rows = res_df[~res_df["model"].str.startswith("Baseline")]
    best = ml_rows.loc[ml_rows["pooled_rho"].idxmax(), "model"]
    model = models()[best].fit(df[feature_cols].to_numpy(), df[target_col].to_numpy())

    if args.plot or not args.demo:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        csv_out = RESULTS_DIR / f"e4_{tag}.csv"
        res_df.to_csv(csv_out, index=False, encoding="utf-8-sig")
        print(f"\n評估結果已存至：{csv_out}")
        save_plots(res_df, oof_preds, df, target_col, tag)

    if args.demo or args.no_save_model:
        if args.demo:
            print(f"\n（demo 模式不存模型）最佳：{best}")
        return

    import joblib
    (ROOT / "models").mkdir(exist_ok=True)
    model_path = ROOT / "models" / f"{args.target}.joblib"
    joblib.dump({"model": model, "columns": feature_cols, "scale": args.scale}, model_path)
    print(f"\n最佳模型 {best} 已存到 {model_path}")


if __name__ == "__main__":
    main()