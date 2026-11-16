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
