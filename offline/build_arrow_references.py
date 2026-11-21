
"""從 Acapella Arrow 資料集建立測試用的代理參考旋律。"""

import json
import sys
from pathlib import Path

import librosa
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scoring.extract_dataset import read_arrow_audio
from scoring.pitch_utils import detect_pitch, hz_to_midi, segment_notes


def main():
    for i in range(2, 7):
        song_id = f"song{i}"

        arrow_dir = ROOT / "data" / "datasets" / "acapella_hf" / song_id
        arrow_files = sorted(arrow_dir.glob("*.arrow"))

        if not arrow_files:
            raise FileNotFoundError(f"{song_id}: 找不到 Arrow 檔案")

        # 選擇 singer_id=0 作為測試用代理參考
        reference = None

        for arrow_path in arrow_files:
            for singer_id, y, sr in read_arrow_audio(arrow_path):
                if singer_id == 0:
                    reference = (y, sr)
                    break
            if reference is not None:
                break

        if reference is None:
            raise ValueError(f"{song_id}: 找不到 singer_id=0")

        y, sr = reference

        # 雙聲道轉單聲道
        if y.ndim == 2:
            y = np.mean(y, axis=1)

        # 統一取樣率
        if sr != 22050:
            y = librosa.resample(
                y,
                orig_sr=sr,
                target_sr=22050
            )
            sr = 22050

        print(f"[{song_id}] 偵測音高...", flush=True)

        times, f0, voiced, rms = detect_pitch(
            y, sr, method="pyin"
        )

        midi = hz_to_midi(f0)
        notes = segment_notes(times, midi)

        song = {
            "title": song_id,
            "bpm": None,
            "duration": round(len(y) / sr, 3),
            "accompaniment": None,
            "notes": notes,
        }

        out_dir = ROOT / "data" / "songs" / song_id
        out_dir.mkdir(parents=True, exist_ok=True)

        out_path = out_dir / "song.json"

        if out_path.exists():
            raise FileExistsError(f"避免覆蓋現有參考：{out_path}")

        out_path.write_text(
            json.dumps(song, ensure_ascii=False, indent=1),
            encoding="utf-8"
        )

        print(
            f"[{song_id}] 完成：{len(notes)} 個音符",
            flush=True
        )

    print("song2～song6 代理參考旋律全部完成！")


if __name__ == "__main__":
    main()
