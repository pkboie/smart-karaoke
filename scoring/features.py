"""從一次演唱擷取四類特徵（負責人：#5）。

輸入：song (song.json) + trace (trace.json 的 frames)
輸出：features dict

先以 voiced activity 估計全域時間位移，再用固定 DTW 配對搜尋 -6～+5 半音，
最後進行 banded DTW，計算既有 pitch/rhythm/contour/expression 特徵。
"""
from __future__ import annotations

import numpy as np

from .pitch_utils import fold_cents, notes_to_curve

DTW_HOP = 0.05
DTW_BAND_SEC = 1.5
UNVOICED_COST = 3.0
MAX_PITCH_COST = 2.0
STEP_PENALTY = 0.6

MAX_GLOBAL_OFFSET_SEC = 40.0  # 允許長前奏；搜尋中心仍以初始發聲起點為準
OFFSET_LOCAL_SEARCH_SEC = 4.0
MIN_OFFSET_IMPROVEMENT = 0.025
MIN_KEY_IMPROVEMENT = 0.08


# ---------- 1. 準備曲線 ----------

def trace_to_curve(frames, duration, offset_ms=0.0, hop=DTW_HOP):
    """把 frames 轉成固定時間間隔的 (MIDI, RMS) 曲線。"""
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


def _overlapping_curves(ref, usr, lag):
    """正 lag：user 的同一樂句較晚出現。"""
    if lag >= 0:
        length = min(len(ref), len(usr) - lag)
        return ref[:max(length, 0)], usr[lag:lag + max(length, 0)]
    length = min(len(ref) + lag, len(usr))
    return ref[-lag:-lag + max(length, 0)], usr[:max(length, 0)]


def _voiced_bounds(curve, min_run=4):
    """回傳持續有聲區間的首尾 frame，忽略零星的 pYIN 誤判。"""
    voiced = np.isfinite(curve).astype(np.int8)
    if not voiced.any():
        return None
    # 5 frames 內至少 4 frames 有音高才算連續發聲，避免單點雜訊。
    smoothed = np.convolve(voiced, np.ones(5, dtype=int), mode="same")
    active = np.flatnonzero(smoothed >= min_run)
    if not len(active):
        return None
    return int(active[0]), int(active[-1])


def estimate_time_offset(ref, usr, max_offset_sec=MAX_GLOBAL_OFFSET_SEC):
    """估計演唱相對參考的全域延遲（正值代表較晚）。

    採用「起唱點粗估 + 局部旋律驗證」。兩份音訊長度不必相同；
    但若無法確認起始樂句相符，會保守回傳 0。
    這不是能處理任意不同歌詞段落／大幅變速的 subsequence DTW。
    """
    ref = np.asarray(ref, dtype=float)
    usr = np.asarray(usr, dtype=float)
    rb = _voiced_bounds(ref)
    ub = _voiced_bounds(usr)
    if rb is None or ub is None:
        return 0.0

    onset_lag = ub[0] - rb[0]
    max_lag = int(round(max_offset_sec / DTW_HOP))
    if abs(onset_lag) > max_lag:
        return 0.0

    # 只檢查前段旋律，避免把長前奏、尾奏或漏唱誤當成整首長度相同。
    # 限制於兩邊都可能存在的首 25 秒，而不是在整首中找相似副歌。
    window = int(round(25.0 / DTW_HOP))
    start = rb[0]
    stop = min(len(ref), start + window)
    if stop - start < 60:
        return 0.0
    target = ref[start:stop]
    target_voiced = np.isfinite(target)
    if target_voiced.sum() < 35:
        return 0.0

    def evaluate(lag):
        # lag = user 時間 - 參考時間。兩者在同一參考區段比較。
        j0, j1 = start + lag, stop + lag
        if j0 < 0 or j1 > len(usr):
            return None
        sample = usr[j0:j1]
        a, b = target_voiced, np.isfinite(sample)
        count = int(np.count_nonzero(a & b))
        if count < max(30, int(0.15 * a.sum())):
            return None
        overlap = 2.0 * count / max(1, (a.sum() + b.sum()))
        if overlap < 0.30:
            return None

        # 用旋律相似度驗證，容許整體移調（±6）及八度差。
        diff = sample[a & b] - target[a & b]
        errors = [
            float(np.median(np.abs(fold_cents(diff - k)) / 100.0))
            for k in range(-6, 6)
        ]
        pitch_error = min(errors)
        # 若旋律吻合很弱，禁止只憑發聲重疊決定偏移。
        if pitch_error > 1.75:
            return None
        score = 0.60 * overlap + 0.40 * (1.0 - pitch_error / 3.0)
        return score, count, pitch_error

    radius = int(round(OFFSET_LOCAL_SEARCH_SEC / DTW_HOP))
    candidates = range(max(-max_lag, onset_lag - radius),
                       min(max_lag, onset_lag + radius) + 1)
    ranked = []
    for lag in candidates:
        measured = evaluate(lag)
        if measured is not None:
            score, count, error = measured
            # 細微偏好更靠近起唱點的解，降低重複樂句誤配。
            score -= 0.002 * abs(lag - onset_lag) * DTW_HOP
            ranked.append((score, -abs(lag - onset_lag), -abs(lag), lag))

    if not ranked:
        return 0.0
    best = max(ranked)
    best_lag = best[-1]
    baseline = evaluate(0)
    if baseline is not None and best_lag != 0:
        # 若不偏移的證據差不多，就避免過度修正。
        if best[0] - baseline[0] < MIN_OFFSET_IMPROVEMENT:
            return 0.0
    return round(best_lag * DTW_HOP, 3)


# ---------- 2. DTW ----------

def banded_dtw(ref, usr, band):
    """原有 Sakoe-Chiba band DTW；回傳 (ref_index, user_index) path。"""
    n, m = len(ref), len(usr)
    INF = 1e18
    D = np.full((n + 1, 2 * band + 3), INF)
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

    D[0, band + 1] = 0.0
    for i in range(1, n + 1):
        for j in range(max(1, i - band), min(m, i + band) + 1):
            c = cost(i - 1, j - 1)
            opts = (get(i - 1, j - 1),
                    get(i - 1, j) + STEP_PENALTY,
                    get(i, j - 1) + STEP_PENALTY)
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


def _shift_alignment_metrics(ref, corrected, path):
    """評估移調候選：實際配對音高 + 非對角步數 + voiced 覆蓋率。"""
    if not path:
        return float("inf"), float("inf")

    ix = np.fromiter((i for i, _ in path), dtype=int)
    jx = np.fromiter((j for _, j in path), dtype=int)
    a, b = ref[ix], corrected[jx]
    valid_a, valid_b = np.isfinite(a), np.isfinite(b)
    paired = valid_a & valid_b
    pair_count = int(paired.sum())
    if pair_count < max(3, int(0.05 * min(np.isfinite(ref).sum(),
                                        np.isfinite(corrected).sum()))):
        return float("inf"), float("inf")

    err = np.abs(fold_cents(b[paired] - a[paired])) / 100.0
    # 用實際音高誤差決定移調，而非只用有大量 silence=0 的 DTW 均值。
    pitch_error = float(np.mean(np.minimum(err, MAX_PITCH_COST)))
    unmatched = int(np.count_nonzero(valid_a ^ valid_b))
    non_diagonal = int(np.count_nonzero((np.diff(ix) == 0) |
                                          (np.diff(jx) == 0)))
    # 仍使用 DTW 的 unvoiced cost 與 step penalty；正規化不讓長音支配結果。
    cost = (pitch_error +
            0.35 * UNVOICED_COST * unmatched / len(path) +
            0.35 * STEP_PENALTY * non_diagonal / len(path))
    return cost, pitch_error


def estimate_key_shift(ref, usr, max_shift=12, max_lag=30):
    """以固定的 DTW 配對估計移調，避免每個候選 shift 重排樂句。

    回傳 (user_minus_reference_semitones, median_pitch_error_semitones)。
    只有在有足夠配對、對 0 移調有明顯改善且最佳解明確時才移調。
    注意：僅靠 fold_cents 無法辨認整整一個八度的差異。
    """
    ref = np.asarray(ref, dtype=float)
    usr = np.asarray(usr, dtype=float)
    if not np.isfinite(ref).any() or not np.isfinite(usr).any():
        return 0, float("inf")

    # One common path for every shift: shift candidates cannot change matching.
    band = int(DTW_BAND_SEC / DTW_HOP)
    path = banded_dtw(ref, usr, band)
    if not path:
        return 0, float("inf")
    ix = np.fromiter((i for i, _ in path), dtype=int)
    jx = np.fromiter((j for _, j in path), dtype=int)
    paired = np.isfinite(ref[ix]) & np.isfinite(usr[jx])
    # Unique paired reference indices avoid giving duplicated DTW steps extra votes.
    ref_indices = ix[paired]
    usr_indices = jx[paired]
    if len(ref_indices):
        _, unique_positions = np.unique(ref_indices, return_index=True)
        ref_indices = ref_indices[unique_positions]
        usr_indices = usr_indices[unique_positions]

    voiced_ref = int(np.isfinite(ref).sum())
    voiced_usr = int(np.isfinite(usr).sum())
    required = max(30, int(0.20 * min(voiced_ref, voiced_usr)))
    if len(ref_indices) < required:
        return 0, float("inf")

    differences = usr[usr_indices] - ref[ref_indices]
    # Quantile/median error is robust to occasional octave mistakes and bad notes.
    errors = {
        shift: float(np.median(np.abs(fold_cents(differences - shift)) / 100.0))
        for shift in range(-6, 6)
    }
    ranked = sorted(errors, key=lambda shift: (errors[shift], abs(shift), shift))
    best, second = ranked[0], ranked[1]
    if best == 0:
        return 0, errors[0]
    # Reject weak or ambiguous shifts, rather than forcing a boundary solution.
    if (errors[0] - errors[best] < MIN_KEY_IMPROVEMENT or
            errors[second] - errors[best] < 0.08 or
            errors[best] > 1.0):
        return 0, errors[0]
    return best, errors[best]


# ---------- 3 & 4. 特徵 ----------

def extract_features(song, frames, offset_ms=0.0):
    notes = song["notes"]
    duration = song.get("duration") or (notes[-1]["end"] + 2.0)

    ref = notes_to_curve(notes, duration, hop=DTW_HOP)
    # 用完整錄音時間軸估計 offset，不能先截斷成參考曲長度。
    # 例：參考 75 秒、歌手第 25 秒才開始唱，原版會丟掉歌手後半段。
    last_frame_sec = max((float(f["t"]) for f in frames), default=0.0)
    full_duration = max(duration, last_frame_sec - offset_ms / 1000.0 + DTW_HOP)
    usr_full, _ = trace_to_curve(frames, full_duration, offset_ms, hop=DTW_HOP)
    offset_sec = estimate_time_offset(ref, usr_full)

    # 在同一個參考時間軸上重新取樣，既有 DTW 和 per_note 邏輯不動。
    usr, usr_rms = trace_to_curve(
        frames, duration, offset_ms=offset_ms + offset_sec * 1000.0,
        hop=DTW_HOP,
    )
    n = min(len(ref), len(usr))
    ref, usr, usr_rms = ref[:n], usr[:n], usr_rms[:n]

    band = int(DTW_BAND_SEC / DTW_HOP)
    key_shift, shift_error = estimate_key_shift(ref, usr)
    if shift_error > 2.0:
        key_shift = 0
    usr_aligned = usr - key_shift
    path = banded_dtw(ref, usr_aligned, band)

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

    # 旋律走向：相鄰兩個音的音程（保留既有計算方式）
    interval_err = []
    for p, q in zip(per_note, per_note[1:]):
        if p["sung_midi"] is None or q["sung_midi"] is None:
            interval_err.append(12.0)
            continue
        ref_iv = q["target_midi"] - p["target_midi"]
        usr_iv = q["sung_midi"] - p["sung_midi"]
        interval_err.append(abs(usr_iv - ref_iv))
    interval_err = np.array(interval_err) if interval_err else np.array([12.0])

    # 表現力：長音顫音幅度、音量起伏（保留既有計算方式）
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
        "offset_sec": float(offset_sec),
        "key_shift": int(key_shift),
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
    """輸出原本 10 個特徵 + offset_sec/key_shift，不含 per_note。"""
    row = {}
    for group, vals in features.items():
        if group == "per_note":
            continue
        if group in ("offset_sec", "key_shift"):
            row[group] = vals
            continue
        for k, v in vals.items():
            row[f"{group}.{k}"] = v
    return row
