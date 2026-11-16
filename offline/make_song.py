"""把一首歌轉成卡拉 OK 用的 song.json（負責人：#5）。

流程：原曲 → Demucs 分離人聲/伴奏 → 人聲音高偵測 → 切音符 → song.json

用法：
    python offline/make_song.py 原曲.mp3 --id song1 --title "歌名" --bpm 76
    python offline/make_song.py vocals.wav --id demo --no-demucs   # 已經是乾淨人聲時

輸出：data/songs/<id>/ 底下的 song.json、accompaniment.wav、vocals.wav
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.pitch_utils import detect_pitch, hz_to_midi, segment_notes  # noqa: E402


def run_demucs(src: Path, workdir: Path) -> tuple[Path, Path]:
    """呼叫 Demucs（pip install demucs），回傳 (vocals.wav, no_vocals.wav)。"""
    subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals",
                    "-o", str(workdir), str(src)], check=True)
    out = next(workdir.glob(f"*/{src.stem}"))
    return out / "vocals.wav", out / "no_vocals.wav"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path)
    ap.add_argument("--id", required=True, help="歌曲資料夾名稱，例如 song1")
    ap.add_argument("--title", default=None)
    ap.add_argument("--bpm", type=float, default=None)
    ap.add_argument("--no-demucs", action="store_true", help="輸入已是乾淨人聲時使用")
    ap.add_argument("--accompaniment", type=Path, default=None, help="--no-demucs 時可另外指定伴奏檔")
    ap.add_argument("--method", default="pyin", choices=["pyin", "yin", "crepe"])
    args = ap.parse_args()

    import librosa
    import soundfile as sf

    out_dir = ROOT / "data" / "songs" / args.id
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.no_demucs:
        vocals_path, acc_path = args.audio, args.accompaniment
    else:
        vocals_path, acc_path = run_demucs(args.audio, out_dir / "_demucs")

    y, sr = librosa.load(vocals_path, sr=22050, mono=True)
    sf.write(out_dir / "vocals.wav", y, sr)
    if acc_path is not None:
        shutil.copy(acc_path, out_dir / "accompaniment.wav")

    print(f"[1/2] 偵測音高（{args.method}）…")
    times, f0, voiced, _ = detect_pitch(y, sr, method=args.method)
    midi = hz_to_midi(f0)

    print("[2/2] 切音符…")
    notes = segment_notes(times, midi)

    song = {
        "title": args.title or args.id,
        "bpm": args.bpm,
        "duration": round(len(y) / sr, 3),
        "accompaniment": "accompaniment.wav" if (out_dir / "accompaniment.wav").exists() else None,
        "notes": notes,
    }
    (out_dir / "song.json").write_text(json.dumps(song, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成：{len(notes)} 個音符 → {out_dir / 'song.json'}")
    print("提醒：自動結果一定會有錯，請用前端或手動檢查並修正 lyric 與錯誤音符。")


if __name__ == "__main__":
    main()
