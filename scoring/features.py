"""從一次演唱擷取四類特徵（負責人：#5）。

輸入：song（song.json）＋ trace（trace.json 的 frames）
輸出：features dict（就是 features.json 的內容）

流程：
1. 兩邊都轉成每 50 ms 一個值的音高曲線
2. 用 DTW（banded，Sakoe-Chiba）找出演唱與原曲的對應時間
3. 依對應結果，算每個音符的音高誤差與開始時間偏差
4. 彙整成 pitch / rhythm / contour / expression 四類
"""
from __future__ import annotations

import numpy as np

from .pitch_utils import fold_cents, notes_to_curve

DTW_HOP = 0.05      # DTW 用 50 ms 一格，3 分鐘的歌約 3600 格
DTW_BAND_SEC = 1.5  # 允許演唱與原曲最多差 1.5 秒
UNVOICED_COST = 3.0  # 一邊有聲一邊沒聲時的代價（單位：半音）
MAX_PITCH_COST = 2.0  # 音高差的代價上限（半音），避免 DTW 為了配對音高而亂扭時間
STEP_PENALTY = 0.6   # 每走一步非對角線的額外代價，讓 DTW 傾向「時間照順序走」


# ---------- 1. 準備曲線 ----------

def trace_to_curve(frames, duration, offset_ms=0.0, hop=DTW_HOP):
    """把前端送來的 frames 轉成固定間隔的曲線；回傳 (midi_curve, rms_curve)。"""
    n = int(np.ceil(duration / hop)) + 1
    midi = np.full(n, np.nan)
    rms = np.zeros(n)
    cnt = np.zeros(n)
    for f in frames:
        t = f["t"] - offset_ms / 1000.0
        i = int(round(t / hop))
        if 0 <= i < n:
            rms[i] += f.get("rms", 0.0)
            cnt[i] += 1
            if f.get("voiced") and f.get("midi") is not None:
                midi[i] = f["midi"] if np.isnan(midi[i]) else (midi[i] + f["midi"]) / 2
    rms = np.where(cnt > 0, rms / np.maximum(cnt, 1), 0.0)
    return midi, rms


# ---------- 2. DTW ----------

def banded_dtw(ref, usr, band):
    """ref、usr：音高曲線（NaN = 沒聲音）。回傳 path：list of (i_ref, j_usr)。

    cost = 折回八度後的音高差（半音），有聲對沒聲給固定代價。
    只在 |i - j| <= band 的範圍內計算，複雜度 O(N * band)。
    """
    n, m = len(ref), len(usr)
    INF = 1e18
    D = np.full((n + 1, 2 * band + 3), INF)  # D[i, k] 對應 j = i + k - band - 1
    back = np.zeros((n + 1, 2 * band + 3), dtype=np.int8)

    def cost(i, j):
        a, b = ref[i], usr[j]
        if np.isnan(a) and np.isnan(b):
            return 0.0
        if np.isnan(a) or np.isnan(b):
            return UNVOICED_COST
        return min(abs(fold_cents(b - a)) / 100.0, MAX_PITCH_COST)

    def get(i, j):
        k = j - i + band + 1
        if i < 0 or j < 0 or k < 0 or k >= D.shape[1]:
            return INF
        return D[i, k]

    D[0, band + 1] = 0.0  # (i=0, j=0) 的「前一格」
    for i in range(1, n + 1):
        for j in range(max(1, i - band), min(m, i + band) + 1):
            c = cost(i - 1, j - 1)
            opts = (get(i - 1, j - 1), get(i - 1, j) + STEP_PENALTY, get(i, j - 1) + STEP_PENALTY)
            b = int(np.argmin(opts))
            D[i, j - i + band + 1] = c + opts[b]
            back[i, j - i + band + 1] = b

    i, j = n, min(m, n + band)
    path = []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        b = back[i, j - i + band + 1]
        if b == 0:
            i, j = i - 1, j - 1
        elif b == 1:
            i -= 1
        else:
            j -= 1
    return path[::-1]


# ---------- 3 & 4. 特徵 ----------

def extract_features(song, frames, offset_ms=0.0):
    notes = song["notes"]
    duration = song.get("duration") or (notes[-1]["end"] + 2.0)

    ref = notes_to_curve(notes, duration, hop=DTW_HOP)
    usr, usr_rms = trace_to_curve(frames, duration, offset_ms, hop=DTW_HOP)
    n = min(len(ref), len(usr))
    ref, usr, usr_rms = ref[:n], usr[:n], usr_rms[:n]

    band = int(DTW_BAND_SEC / DTW_HOP)
    path = banded_dtw(ref, usr, band)
    ref_to_usr = {}
    for i, j in path:
        ref_to_usr.setdefault(i, []).append(j)

    per_note = []
    for idx, note in enumerate(notes):
        a = int(round(note["start"] / DTW_HOP))
        b = max(a + 1, int(round(note["end"] / DTW_HOP)))
        js = sorted({j for i in range(a, min(b, n)) for j in ref_to_usr.get(i, [])})
        sung = [usr[j] for j in js if not np.isnan(usr[j])]
        coverage = len(sung) / max(1, b - a)
        if sung:
            sung_med = float(np.median(sung))
            cents = float(fold_cents(sung_med - note["midi"]))
            voiced_js = [j for j in js if not np.isnan(usr[j])]
            onset_ms = (voiced_js[0] - a) * DTW_HOP * 1000.0
        else:
            sung_med, cents, onset_ms = None, None, None
        per_note.append({"index": idx, "lyric": note.get("lyric", ""), "start": note["start"],
                         "target_midi": note["midi"], "sung_midi": sung_med,
                         "cent_error": cents, "onset_ms": onset_ms, "coverage": coverage})

    sung_notes = [p for p in per_note if p["cent_error"] is not None and p["coverage"] >= 0.3]
    cents = np.array([abs(p["cent_error"]) for p in sung_notes]) if sung_notes else np.array([600.0])
    onsets = np.array([p["onset_ms"] for p in sung_notes]) if sung_notes else np.array([1000.0])

    # 旋律走向：相鄰兩個音的音程（不折八度，以演唱者自己的音域為準）
    interval_err = []
    for p, q in zip(per_note, per_note[1:]):
        if p["sung_midi"] is None or q["sung_midi"] is None:
            interval_err.append(12.0)
            continue
        ref_iv = q["target_midi"] - p["target_midi"]
        usr_iv = q["sung_midi"] - p["sung_midi"]
        interval_err.append(abs(usr_iv - ref_iv))
    interval_err = np.array(interval_err) if interval_err else np.array([12.0])

    # 表現力：長音的顫音幅度、音量起伏
    vib = []
    for note in notes:
        if note["end"] - note["start"] < 0.6:
            continue
        a, b = int(note["start"] / DTW_HOP), int(note["end"] / DTW_HOP)
        js = sorted({j for i in range(a, min(b, n)) for j in ref_to_usr.get(i, [])})
        seg = np.array([usr[j] for j in js if not np.isnan(usr[j])])
        if len(seg) >= 6:
            vib.append(float(np.std(seg - np.median(seg)) * 100))
    voiced_rms = usr_rms[~np.isnan(usr)]

    return {
        "pitch": {
            "median_abs_cents": float(np.median(cents)),
            "hit_rate_50c": float(np.mean(cents < 50)),
            "hit_rate_100c": float(np.mean(cents < 100)),
        },
        "rhythm": {
            "median_abs_onset_ms": float(np.median(np.abs(onsets))),
            "early_rate": float(np.mean(onsets < -150)),
            "late_rate": float(np.mean(onsets > 150)),
        },
        "contour": {
            "interval_accuracy": float(np.mean(interval_err < 1.0)),
            "note_coverage": float(np.mean([p["coverage"] >= 0.3 for p in per_note])),
        },
        "expression": {
            "vibrato_cents": float(np.mean(vib)) if vib else 0.0,
            "dynamics_std": float(np.std(voiced_rms) / (np.mean(voiced_rms) + 1e-9)) if len(voiced_rms) else 0.0,
        },
        "per_note": per_note,
    }


def flatten(features):
    """把 features 攤平成一列數字（給模型訓練用），不含 per_note。"""
    row = {}
    for group, vals in features.items():
        if group == "per_note":
            continue
        for k, v in vals.items():
            row[f"{group}.{k}"] = v
    return row
