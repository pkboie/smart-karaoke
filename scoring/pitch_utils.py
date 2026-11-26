"""共用的音高工具：Hz/MIDI 換算、音高偵測、切音符。

offline/、scoring/、experiments/ 都會 import 這個檔案。
"""
from __future__ import annotations

import numpy as np

HOP_SEC = 0.01  # 每 10 ms 一個 frame


def hz_to_midi(f0):
    f0 = np.asarray(f0, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return 69 + 12 * np.log2(f0 / 440.0)


def fold_cents(diff_semitones):
    """把音高差（半音）換成 cents，並折回 [-600, 600)，忽略八度。"""
    c = np.asarray(diff_semitones, dtype=float) * 100.0
    return ((c % 1200) + 1800) % 1200 - 600


def detect_pitch(y, sr, method="pyin", fmin=65.0, fmax=1000.0):
    """回傳 (times, f0_hz, voiced, rms)，每 10 ms 一筆。

    method: "pyin"（準、慢）、"yin"（快）、"crepe"（需另外安裝 torchcrepe）

    注意：fmin=65Hz 約為 MIDI 36。靠近下限的偵測需要進一步驗證，
    但不能僅因音高低就直接刪除真實低音。
    """
    import librosa

    hop = int(round(sr * HOP_SEC))
    frame = 2048 if sr >= 32000 else 1024
    if method == "pyin":
        f0, voiced, _ = librosa.pyin(
            y, fmin=fmin, fmax=fmax, sr=sr,
            frame_length=frame, hop_length=hop,
        )
        voiced = voiced & ~np.isnan(f0)
    elif method == "yin":
        f0 = librosa.yin(
            y, fmin=fmin, fmax=fmax, sr=sr,
            frame_length=frame, hop_length=hop,
        )
        rms_tmp = librosa.feature.rms(
            y=y, frame_length=frame, hop_length=hop
        )[0]
        voiced = rms_tmp > 0.02 * (rms_tmp.max() + 1e-9)
    elif method == "crepe":
        import torch
        import torchcrepe
        audio = torch.tensor(
            librosa.resample(y, orig_sr=sr, target_sr=16000)
        )[None]
        f0_t, per = torchcrepe.predict(
            audio, 16000, hop_length=160,
            fmin=fmin, fmax=fmax,
            model="tiny", return_periodicity=True,
            batch_size=512,
        )
        f0 = f0_t[0].numpy()
        voiced = per[0].numpy() > 0.5
    else:
        raise ValueError(method)

    rms = librosa.feature.rms(
        y=y, frame_length=frame, hop_length=hop
    )[0]
    n = min(len(f0), len(rms))
    f0, voiced, rms = f0[:n], voiced[:n], rms[:n]
    f0 = np.where(voiced, f0, np.nan)
    times = np.arange(n) * HOP_SEC
    return times, f0, voiced, rms


def _median_within_voiced_runs(midi, size):
    """只在連續有聲區間平滑；NaN 不得當作 MIDI 0 參與中位數。"""
    from scipy.ndimage import median_filter

    m = np.asarray(midi, dtype=float)
    smooth = np.full(m.shape, np.nan, dtype=float)
    valid = np.isfinite(m)
    if not valid.any():
        return smooth

    transitions = np.diff(np.r_[False, valid, False].astype(np.int8))
    starts = np.flatnonzero(transitions == 1)
    ends = np.flatnonzero(transitions == -1)
    for start, end in zip(starts, ends):
        length = end - start
        window = min(int(size), length)
        if window % 2 == 0:
            window -= 1
        if window >= 3:
            smooth[start:end] = median_filter(
                m[start:end], size=window, mode="nearest"
            )
        else:
            smooth[start:end] = m[start:end]
    return smooth


def segment_notes(times, midi, min_dur=0.10, merge_gap=0.03):
    """規則式切音符：有聲段內中位數平滑 → 半音量化 → 合併 → 時長過濾。

    不把靜音 NaN 填成 0，因此不會在有聲片段的頭尾製造虛假的低音。
    已知限制：相同音高的相鄰歌詞可能合併。
    """
    times = np.asarray(times, dtype=float)
    m = np.asarray(midi, dtype=float)
    if times.shape != m.shape:
        raise ValueError("times and midi must have the same shape")
    if len(times) > 1 and np.any(np.diff(times) <= 0):
        raise ValueError("times must be strictly increasing")

    smooth = _median_within_voiced_runs(m, 5)
    q = np.where(np.isfinite(smooth), np.round(smooth), np.nan)
    notes, cur = [], None
    for t, v in zip(times, q):
        if not np.isfinite(v):
            if cur is not None:
                notes.append(cur)
                cur = None
            continue
        if cur is not None and v == cur["midi"] and t - cur["end"] <= merge_gap + HOP_SEC:
            cur["end"] = float(t + HOP_SEC)
        else:
            if cur is not None:
                notes.append(cur)
            cur = {"start": float(t), "end": float(t + HOP_SEC), "midi": int(v)}
    if cur is not None:
        notes.append(cur)
    notes = [n for n in notes if n["end"] - n["start"] >= min_dur]
    for n in notes:
        n["start"] = round(n["start"], 3)
        n["end"] = round(n["end"], 3)
        n["lyric"] = ""
    return notes


def notes_to_curve(notes, duration, hop=HOP_SEC):
    """把 song.json 的 notes 轉成每 hop 秒一個值的參考音高曲線。"""
    n = int(np.ceil(duration / hop)) + 1
    curve = np.full(n, np.nan)
    for note in notes:
        a = int(round(note["start"] / hop))
        b = int(round(note["end"] / hop))
        curve[a:b] = note["midi"]
    return curve


def segment_notes_v2(
    times,
    midi,
    min_dur=0.12,
    max_missing_sec=0.20,
    max_pitch_diff=1.0,
    smooth_frames=11,
):
    """改善版切音符：短空白內插、有聲段平滑、相鄰同音合併。"""
    times = np.asarray(times, dtype=float)
    m = np.asarray(midi, dtype=float).copy()
    if len(times) != len(m):
        raise ValueError("times and midi must have the same length")
    if len(m) == 0:
        return []
    if len(times) > 1 and np.any(np.diff(times) <= 0):
        raise ValueError("times must be strictly increasing")
    if smooth_frames < 1:
        raise ValueError("smooth_frames must be >= 1")
    if max_missing_sec < 0 or max_pitch_diff < 0:
        raise ValueError("Gap and pitch thresholds must be nonnegative")

    valid_indices = np.flatnonzero(np.isfinite(m))
    if len(valid_indices) == 0:
        return []
    for left, right in zip(valid_indices[:-1], valid_indices[1:]):
        if right == left + 1:
            continue
        missing_duration = times[right] - times[left] - HOP_SEC
        pitch_difference = abs(m[right] - m[left])
        if missing_duration <= max_missing_sec and pitch_difference <= max_pitch_diff:
            m[left + 1:right] = np.linspace(
                m[left], m[right], right - left + 1
            )[1:-1]

    smoothed = _median_within_voiced_runs(m, smooth_frames)
    quantized = np.where(np.isfinite(smoothed), np.round(smoothed), np.nan)
    notes = []
    current = None
    for t, pitch in zip(times, quantized):
        if not np.isfinite(pitch):
            if current is not None:
                notes.append(current)
                current = None
            continue
        pitch = int(pitch)
        if current is not None and pitch == current["midi"]:
            current["end"] = float(t + HOP_SEC)
        else:
            if current is not None:
                notes.append(current)
            current = {"start": float(t), "end": float(t + HOP_SEC), "midi": pitch}
    if current is not None:
        notes.append(current)

    merged = []
    for note in notes:
        if not merged:
            merged.append(note.copy())
            continue
        prev = merged[-1]
        gap = note["start"] - prev["end"]
        if 0 <= gap <= 0.08 and note["midi"] == prev["midi"]:
            prev["end"] = note["end"]
        else:
            merged.append(note.copy())

    result = []
    for note in merged:
        if note["end"] - note["start"] < min_dur:
            continue
        result.append({
            "start": round(note["start"], 3),
            "end": round(note["end"], 3),
            "midi": note["midi"],
            "lyric": "",
        })
    return result
