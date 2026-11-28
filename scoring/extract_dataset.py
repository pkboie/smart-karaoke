"""把資料集的錄音批次轉成特徵表 features.csv（負責人：#5，給 #3 訓練用）。

每首歌需要一份參考 song.json（用 offline/make_song.py 從原曲產生）。

資料夾結構範例（Acapella）：
    data/datasets/acapella/song1/*.wav   ← 同一首歌、不同歌手的錄音
    data/songs/acapella_song1/song.json  ← 這首歌的參考旋律

用法：
    python scoring/extract_dataset.py --audio-dir data/datasets/acapella/song1 \
        --song acapella_song1 --out data/features/acapella_song1.csv

之後由 #3 把評審分數（labels）依檔名合併進來，再跑 scoring/train.py。
"""
from __future__ import annotations

import argparse
import csv
import json
import io
import pyarrow as pa
import pyarrow.ipc as ipc
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.features import extract_features, flatten  # noqa: E402
from scoring.pitch_utils import detect_pitch, hz_to_midi  # noqa: E402


def wav_to_frames(path, method="pyin"):
    import librosa
    import numpy as np

    y, sr = librosa.load(path, sr=22050, mono=True)
    times, f0, voiced, rms = detect_pitch(y, sr, method=method)
    midi = hz_to_midi(f0)
    return [{"t": float(t), "midi": None if np.isnan(m) else float(m), "voiced": bool(v), "rms": float(r)}
            for t, m, v, r in zip(times, midi, voiced, rms)]

def audio_to_frames(y, sr, method="pyin"):
    """把記憶體中的音訊轉成音高 frames。"""
    import librosa
    import numpy as np

    # 雙聲道轉單聲道
    if y.ndim == 2:
        y = np.mean(y, axis=1)

    # 統一取樣率
    if sr != 22050:
        y = librosa.resample(y, orig_sr=sr, target_sr=22050)
        sr = 22050

    times, f0, voiced, rms = detect_pitch(y, sr, method=method)
    midi = hz_to_midi(f0)

    return [
        {
            "t": float(t),
            "midi": None if np.isnan(m) else float(m),
            "voiced": bool(v),
            "rms": float(r),
        }
        for t, m, v, r in zip(times, midi, voiced, rms)
    ]

def read_arrow_audio(arrow_path):
    """逐筆讀取 Arrow 中的歌手音訊。"""
    import soundfile as sf

    with pa.memory_map(str(arrow_path), "r") as source:
        reader = ipc.open_stream(source)

        for batch in reader:
            audio_col = batch.column(
                batch.schema.get_field_index("audio")
            )
            singer_col = batch.column(
                batch.schema.get_field_index("singer_id")
            )

            for i in range(batch.num_rows):
                audio = audio_col[i].as_py()
                singer_id = int(singer_col[i].as_py())

                y, sr = sf.read(io.BytesIO(audio["bytes"]))

                yield singer_id, y, sr



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio-dir", type=Path,
                    help="WAV 音檔資料夾")
    ap.add_argument("--arrow-dir", type=Path,
                    help="Acapella Arrow 資料集資料夾")
    ap.add_argument("--song", required=True,
                    help="data/songs/ 底下的參考歌曲 id")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--method", default="pyin")
    args = ap.parse_args()

    # 必須選擇一種音訊來源
    if (args.audio_dir is None) == (args.arrow_dir is None):
        ap.error("請選擇 --audio-dir 或 --arrow-dir，不能同時指定")

    # 讀取參考歌曲
    song_path = ROOT / "data" / "songs" / args.song / "song.json"

    if not song_path.exists():
        raise FileNotFoundError(
            f"找不到參考歌曲：{song_path}"
        )

    song = json.loads(song_path.read_text(encoding="utf-8"))
    rows = []

    # ---------- Arrow 模式 ----------
    if args.arrow_dir is not None:
        arrow_files = sorted(args.arrow_dir.glob("*.arrow"))

        if not arrow_files:
            raise FileNotFoundError(
                f"找不到 Arrow 檔案：{args.arrow_dir}"
            )

        for arrow_path in arrow_files:
            for singer_id, y, sr in read_arrow_audio(arrow_path):

                frames = audio_to_frames(y, sr, args.method)
                feats = extract_features(song, frames, apply_key_shift=True)

                rows.append({
                    "song": args.song,
                    "singer_id": singer_id,
                    **flatten(feats)
                })

                print(
                    f"song={args.song}, singer_id={singer_id} 完成",
                    flush=True
                )

    # ---------- WAV 模式 ----------
    else:
        wav_files = sorted(args.audio_dir.glob("*.wav"))

        if not wav_files:
            raise FileNotFoundError(
                f"找不到 WAV 檔案：{args.audio_dir}"
            )

        for wav in wav_files:
            frames = wav_to_frames(wav, args.method)
            feats = extract_features(song, frames, apply_key_shift=True)

            rows.append({
                "file": wav.name,
                "song": args.song,
                **flatten(feats)
            })

            print(f"{wav.name} 完成", flush=True)

    # ---------- 輸出 CSV ----------
    if not rows:
        raise ValueError("沒有可輸出的特徵資料")

    args.out.parent.mkdir(parents=True, exist_ok=True)

    with args.out.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"完成：{len(rows)} 筆 → {args.out}")



if __name__ == "__main__":
    main()
