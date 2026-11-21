"""把特徵轉成分數與建議（負責人：#3）。

目前預設為「規則式」分數，確保 demo 一定能動。
訓練好模型後（scoring/train.py 會存 models/<target>.joblib），
overall、pitch、rhythm、expression 會自動改由對應模型預測（contour 維持規則式）。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .features import flatten

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"


def lin(x, good, bad):
    """x 在 good 時給 100 分、在 bad 時給 0 分，中間線性內插。"""
    s = (x - bad) / (good - bad) * 100
    return float(np.clip(s, 0, 100))


def rule_scores(f, strict=True):
    tol = 50 if strict else 100
    pitch = 0.5 * lin(f["pitch"]["median_abs_cents"], 10, tol * 2) + \
        0.5 * (f["pitch"]["hit_rate_50c" if strict else "hit_rate_100c"] * 100)
    rhythm = lin(f["rhythm"]["median_abs_onset_ms"], 40, 400)
    contour = 0.6 * f["contour"]["interval_accuracy"] * 100 + 0.4 * f["contour"]["note_coverage"] * 100
    expression = 0.5 * lin(abs(f["expression"]["vibrato_cents"] - 25), 0, 40) + \
        0.5 * lin(abs(f["expression"]["dynamics_std"] - 0.35), 0, 0.5)
    return {"pitch": round(pitch), "rhythm": round(rhythm),
            "contour": round(contour), "expression": round(expression)}


def _predict_with_model(target: str, row: dict[str, float]) -> float | None:
    """若 models/<target>.joblib 存在則載入預測並縮放至 0–100，否則回傳 None。"""
    model_path = MODELS_DIR / f"{target}.joblib"
    if not model_path.exists():
        return None
    import joblib
    bundle = joblib.load(model_path)
    x = np.array([[row[c] for c in bundle["columns"]]])
    pred = float(bundle["model"].predict(x)[0] * bundle.get("scale", 1.0))
    return float(np.clip(pred, 0, 100))


def make_tips(f, scores, max_tips=3):
    tips = []
    bad_pitch = sorted([p for p in f["per_note"] if p["cent_error"] is not None and abs(p["cent_error"]) >= 50],
                       key=lambda p: -abs(p["cent_error"]))
    for p in bad_pitch[:2]:
        direction = "偏高" if p["cent_error"] > 0 else "偏低"
        label = f"「{p['lyric']}」" if p["lyric"] else f"第 {p['index'] + 1} 個音"
        tips.append(f"{p['start']:.1f} 秒的{label}{direction} {abs(p['cent_error']):.0f} cent")
    if f["rhythm"]["early_rate"] > 0.2:
        tips.append("常常搶拍，試著等伴奏的拍點再進")
    elif f["rhythm"]["late_rate"] > 0.2:
        tips.append("常常拖拍，進拍可以再早一點")
    if f["contour"]["note_coverage"] < 0.7:
        tips.append("有不少段落沒有唱到，記得跟著音準線唱完整")
    if scores["expression"] < 50:
        tips.append("長音可以加一點顫音或音量變化，聽起來會比較有感情")
    return tips[:max_tips] or ["表現很穩定，可以挑戰困難模式！"]


def score(features, strict=True):
    s = rule_scores(features, strict=strict)
    row = None

    for target in ("pitch", "rhythm", "expression"):
        if (MODELS_DIR / f"{target}.joblib").exists():
            if row is None:
                row = flatten(features)
            pred = _predict_with_model(target, row)
            if pred is not None:
                s[target] = round(pred)

    overall = 0.4 * s["pitch"] + 0.25 * s["rhythm"] + 0.2 * s["contour"] + 0.15 * s["expression"]
    if (MODELS_DIR / "overall.joblib").exists():
        if row is None:
            row = flatten(features)
        pred_overall = _predict_with_model("overall", row)
        if pred_overall is not None:
            overall = pred_overall

    return {"overall": round(overall), **s, "tips": make_tips(features, s)}