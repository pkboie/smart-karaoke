
from pathlib import Path

import librosa
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "data" / "datasets" / "mir1k" / "MIR-1K"


def load_mir1k(filename):
    audio_path = DATASET_DIR / "Wavfile" / filename
    pitch_path = DATASET_DIR / "PitchLabel" / (
        Path(filename).stem + ".pv"
    )

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    if not pitch_path.is_file():
        raise FileNotFoundError(f"Pitch labels not found: {pitch_path}")

    audio, sr = librosa.load(
        audio_path,
        sr=None,
        mono=False
    )

    if audio.ndim != 2 or audio.shape[0] != 2:
        raise ValueError("Expected a stereo MIR-1K WAV file")

    accompaniment = audio[0]
    vocals = audio[1]

    pitch_labels = np.atleast_1d(np.loadtxt(pitch_path))
    pitch_times = np.arange(
        1, len(pitch_labels) + 1
    ) * 0.02

    return {
        "sample_rate": sr,
        "accompaniment": accompaniment,
        "vocals": vocals,
        "pitch_labels": pitch_labels,
        "pitch_times": pitch_times,
    }


if __name__ == "__main__":
    wav_files = sorted(
        (DATASET_DIR / "Wavfile").glob("*.wav")
    )

    if not wav_files:
        raise FileNotFoundError("No WAV files found in MIR-1K")

    filename = wav_files[0].name
    data = load_mir1k(filename)

    duration = len(data["vocals"]) / data["sample_rate"]

    print("Filename:", filename)
    print("Sample rate:", data["sample_rate"])
    print("Duration:", round(duration, 2), "seconds")
    print("Accompaniment samples:", len(data["accompaniment"]))
    print("Vocal samples:", len(data["vocals"]))
    print("Pitch labels:", len(data["pitch_labels"]))
    print("First pitch time:", data["pitch_times"][0])

import soundfile as sf

sf.write("vocal_test.wav", data["vocals"], data["sample_rate"])
sf.write("accompaniment_test.wav", data["accompaniment"], data["sample_rate"])