"""產生一首「合成的示範歌曲」，沒有版權問題，讓大家第一天就能測試整套系統。

旋律：小星星（公有領域），合成人聲 + 簡單和弦伴奏。
輸出：data/songs/demo/ 底下的 song.json（正確答案）、accompaniment.wav、vocals.wav、full_mix.wav

用法：python offline/make_demo_song.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SR = 22050
BPM = 90
BEAT = 60 / BPM

# (midi, 拍數, 歌詞)
MELODY = [
    (60, 1, "一"), (60, 1, "閃"), (67, 1, "一"), (67, 1, "閃"), (69, 1, "亮"), (69, 1, "晶"), (67, 2, "晶"),
    (65, 1, "滿"), (65, 1, "天"), (64, 1, "都"), (64, 1, "是"), (62, 1, "小"), (62, 1, "星"), (60, 2, "星"),
    (67, 1, "掛"), (67, 1, "在"), (65, 1, "天"), (65, 1, "上"), (64, 1, "放"), (64, 1, "光"), (62, 2, "明"),
    (67, 1, "好"), (67, 1, "像"), (65, 1, "許"), (65, 1, "多"), (64, 1, "小"), (64, 1, "眼"), (62, 2, "睛"),
]
CHORDS = [[48, 52, 55], [48, 52, 55], [53, 57, 60], [48, 52, 55],
          [53, 57, 60], [48, 52, 55], [55, 59, 62], [48, 52, 55]] * 2  # 每個和弦 2 拍
LEAD_IN = 2 * BEAT  # 前奏 2 拍


def tone(freq, dur, harmonics=5, vibrato=0.0):
    t = np.arange(int(dur * SR)) / SR
    f = freq * 2 ** (vibrato * np.sin(2 * np.pi * 5.5 * t) / 12)
    phase = 2 * np.pi * np.cumsum(f) / SR
    y = sum((0.5 / k) * np.sin(k * phase) for k in range(1, harmonics + 1))
    env = np.minimum(1, np.minimum(t / 0.02, (dur - t) / 0.05).clip(0))
    return y * env


def midi_hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def main():
    import soundfile as sf

    out = ROOT / "data" / "songs" / "demo"
    out.mkdir(parents=True, exist_ok=True)

    total_beats = sum(b for _, b, _ in MELODY)
    dur = LEAD_IN + total_beats * BEAT + 1.0
    vocals = np.zeros(int(dur * SR))
    acc = np.zeros(int(dur * SR))

    notes, t = [], LEAD_IN
    for midi, beats, lyric in MELODY:
        d = beats * BEAT
        seg = tone(midi_hz(midi), d * 0.92, vibrato=0.25 if beats >= 2 else 0.0)
        i = int(t * SR)
        vocals[i:i + len(seg)] += seg
        notes.append({"start": round(t, 3), "end": round(t + d * 0.92, 3), "midi": midi, "lyric": lyric})
        t += d

    t = LEAD_IN
    for chord in CHORDS:
        d = 2 * BEAT
        seg = sum(tone(midi_hz(m), d * 0.95, harmonics=2) for m in chord) * 0.25
        i = int(t * SR)
        acc[i:i + len(seg)] += seg
        t += d
    for k in range(int(dur / BEAT)):  # 節拍器
        i = int(k * BEAT * SR)
        click = np.sin(2 * np.pi * 1500 * np.arange(400) / SR) * np.exp(-np.arange(400) / 80)
        acc[i:i + 400] += 0.3 * click

    vocals *= 0.6 / np.abs(vocals).max()
    acc *= 0.5 / np.abs(acc).max()
    sf.write(out / "vocals.wav", vocals, SR)
    sf.write(out / "accompaniment.wav", acc, SR)
    sf.write(out / "full_mix.wav", vocals + acc, SR)

    song = {"title": "Demo：小星星", "bpm": BPM, "duration": round(dur, 3),
            "accompaniment": "accompaniment.wav", "notes": notes}
    (out / "song.json").write_text(json.dumps(song, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成：{out}（{len(notes)} 個音符，{dur:.1f} 秒）")


if __name__ == "__main__":
    main()
