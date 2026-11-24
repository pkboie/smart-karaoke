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
    """
    import librosa

    hop = int(round(sr * HOP_SEC))
    frame = 2048 if sr >= 32000 else 1024
    if method == "pyin":
        f0, voiced, _ = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr,
                                     frame_length=frame, hop_length=hop)
        voiced = voiced & ~np.isnan(f0)
    elif method == "yin":
        f0 = librosa.yin(y, fmin=fmin, fmax=fmax, sr=sr,
                         frame_length=frame, hop_length=hop)
        rms_tmp = librosa.feature.rms(y=y, frame_length=frame, hop_length=hop)[0]
        voiced = rms_tmp > 0.02 * (rms_tmp.max() + 1e-9)
    elif method == "crepe":
        import torch
        import torchcrepe
        audio = torch.tensor(librosa.resample(y, orig_sr=sr, target_sr=16000))[None]
        f0_t, per = torchcrepe.predict(audio, 16000, hop_length=160, fmin=fmin, fmax=fmax,
                                       model="tiny", return_periodicity=True, batch_size=512)
        f0 = f0_t[0].numpy()
        voiced = per[0].numpy() > 0.5
    else:
        raise ValueError(method)

    rms = librosa.feature.rms(y=y, frame_length=frame, hop_length=hop)[0]
    n = min(len(f0), len(rms))
    f0, voiced, rms = f0[:n], voiced[:n], rms[:n]
    f0 = np.where(voiced, f0, np.nan)
    times = np.arange(n) * HOP_SEC
    return times, f0, voiced, rms


def segment_notes(times, midi, min_dur=0.10, merge_gap=0.03):
    """規則式切音符：中位數平滑 → 四捨五入到半音 → 相同音高合併 → 丟掉太短的。

    已知限制：同一個音高連唱兩個字會被合併成一個音符（ML 可以改善的地方）。
    """
    from scipy.ndimage import median_filter

    m = np.array(midi, dtype=float)
    voiced = ~np.isnan(m)
    smooth = m.copy()
    if voiced.any():
        filled = np.where(voiced, m, 0.0)
        smooth = np.where(voiced, median_filter(filled, size=5), np.nan)
    q = np.round(smooth)

    notes, cur = [], None
    for t, v in zip(times, q):
        if np.isnan(v):
            if cur is not None:
                notes.append(cur)
                cur = None
            continue
        if cur is not None and v == cur["midi"] and t - cur["end"] <= merge_gap + HOP_SEC:
            cur["end"] = t + HOP_SEC
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
    """把 song.json 的 notes 轉成每 hop 秒一個值的參考音高曲線（沒有音符的地方是 NaN）。"""
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
    """
    Improved note segmentation for singing vocals.

    Improvements:
    1. Fill short missing-pitch gaps when neighboring pitches agree.
    2. Smooth pitch fluctuations before quantization.
    3. Suppress very short pitch jumps.
    4. Preserve longer rests and meaningful pitch changes.

    Returns notes compatible with song.json v1.
    """
    from scipy.ndimage import median_filter

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

    # ------------------------------------------
    # 1. Fill short missing-pitch gaps
    # ------------------------------------------
    valid = np.isfinite(m)
    valid_indices = np.flatnonzero(valid)

    if len(valid_indices) == 0:
        return []

    for left, right in zip(
        valid_indices[:-1],
        valid_indices[1:],
    ):
        if right == left + 1:
            continue

        missing_duration = (
            times[right] - times[left] - HOP_SEC
        )

        pitch_difference = abs(m[right] - m[left])

        if (
            missing_duration <= max_missing_sec
            and pitch_difference <= max_pitch_diff
        ):
            m[left + 1:right] = np.linspace(
                m[left],
                m[right],
                right - left + 1,
            )[1:-1]

    # ------------------------------------------
    # 2. Median smoothing within voiced regions
    #    Keep long silent gaps as NaN.
    # ------------------------------------------
    valid = np.isfinite(m)
    smoothed = np.full_like(m, np.nan)

    boundaries = np.diff(
        np.r_[False, valid, False].astype(int)
    )

    starts = np.flatnonzero(boundaries == 1)
    ends = np.flatnonzero(boundaries == -1)

    for start, end in zip(starts, ends):
        region = m[start:end]

        if len(region) < 3:
            smoothed[start:end] = region
            continue

        size = min(smooth_frames, len(region))
        if size % 2 == 0:
            size -= 1

        smoothed[start:end] = median_filter(
            region,
            size=size,
            mode="nearest",
        )

    # ------------------------------------------
    # 3. Convert frame pitches into notes
    # ------------------------------------------
    quantized = np.where(
        np.isfinite(smoothed),
        np.round(smoothed),
        np.nan,
    )

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

            current = {
                "start": float(t),
                "end": float(t + HOP_SEC),
                "midi": pitch,
            }

    if current is not None:
        notes.append(current)

    # ------------------------------------------
    # 4. Merge compatible short-gap fragments
    # ------------------------------------------
    merged = []

    for note in notes:
        if not merged:
            merged.append(note.copy())
            continue

        prev = merged[-1]
        gap = note["start"] - prev["end"]

        if (
            0 <= gap <= 0.08
            and note["midi"] == prev["midi"]
        ):
            prev["end"] = note["end"]
        else:
            merged.append(note.copy())

    # ------------------------------------------
    # 5. Remove tiny fragments
    # ------------------------------------------
    result = []

    for note in merged:
        duration = note["end"] - note["start"]

        if duration < min_dur:
            continue

        result.append({
            "start": round(note["start"], 3),
            "end": round(note["end"], 3),
            "midi": note["midi"],
            "lyric": "",
        })

    return result
