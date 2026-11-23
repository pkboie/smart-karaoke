
from pathlib import Path
import argparse

import numpy as np
import soundfile as sf

from mir1k_loader import DATASET_DIR, load_mir1k


SNR_LEVELS = [None, 20, 10, 5, 0, -5]

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "experiments" / "noise_robustness"


def mix_with_snr(vocals, accompaniment, snr_db):
    """
    Mix vocals and accompaniment at a specified SNR.
    None means clean vocals.
    """

    vocals = np.asarray(vocals, dtype=np.float64)
    accompaniment = np.asarray(accompaniment, dtype=np.float64)

    n = min(len(vocals), len(accompaniment))
    vocals = vocals[:n]
    accompaniment = accompaniment[:n]

    if snr_db is None:
        return vocals.copy()

    vocal_power = np.mean(vocals ** 2)
    acc_power = np.mean(accompaniment ** 2)

    if vocal_power <= 0:
        raise ValueError("Vocal audio is silent")

    if acc_power <= 0:
        raise ValueError("Accompaniment audio is silent")

    target_acc_power = vocal_power / (10 ** (snr_db / 10))

    gain = np.sqrt(target_acc_power / acc_power)

    mixed = vocals + gain * accompaniment

    return mixed


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--filename",
        default=None,
        help="MIR-1K WAV filename"
    )

    args = parser.parse_args()

    wav_files = sorted(
        (DATASET_DIR / "Wavfile").glob("*.wav")
    )

    if not wav_files:
        raise FileNotFoundError("No MIR-1K WAV files found")

    filename = args.filename or wav_files[0].name
    data = load_mir1k(filename)

    vocals = data["vocals"]
    accompaniment = data["accompaniment"]
    sr = data["sample_rate"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Input file:", filename)

    for snr in SNR_LEVELS:
        mixed = mix_with_snr(vocals, accompaniment, snr)

        label = "clean" if snr is None else f"{snr}db"

        output_path = OUTPUT_DIR / (
            f"{Path(filename).stem}_{label}.wav"
        )

        # Use floating-point WAV to avoid PCM clipping.
        sf.write(
            output_path,
            mixed,
            sr,
            subtype="FLOAT"
        )

        # Verify the intended SNR numerically.
        if snr is not None:
            noise = mixed - vocals[:len(mixed)]

            signal_power = np.mean(vocals[:len(mixed)] ** 2)
            noise_power = np.mean(noise ** 2)

            actual_snr = 10 * np.log10(
                signal_power / noise_power
            )

            print(
                f"{label:>7}: actual SNR = "
                f"{actual_snr:6.2f} dB"
            )
        else:
            print("  clean: vocals only")

        print("Saved:", output_path)

    print("SNR mixing completed.")


if __name__ == "__main__":
    main()
