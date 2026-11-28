"""Build label-informed experimental v3 features from the highest-rated singer per song.

Run from project root, on a fresh experiment branch:
    python offline/build_features_v3_experimental.py --fix-offline-octave

This tool patches (with backup) the verified offline per-note shift issue if
requested, verifies the patched logic, and extracts 132 rows. It never changes
features.csv, features_v2.csv, demo JSON, or models.

WARNING: Reference singers are chosen from the SAME SONG'S human labels. This
is exploratory and invalid as leak-free LOSO even if the reference singer row
is dropped. Do not report it as an unbiased model evaluation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FEATURES_PY = ROOT / 'scoring' / 'features.py'
OUT_DIR = ROOT / 'data' / 'features'
EXPERIMENT_DIR = OUT_DIR / 'reference_experiments'

# Match the ACTUAL uploaded scoring/features.py (2026-11-28).
# Existing source ALREADY folds octave per frame. The missing part is use of
# key_shift inside per-note metrics. Preserve the current octave handling.
OLD_NOTE = '''        sung = [usr[j] for j in js if not np.isnan(usr[j])]
        coverage = len(sung) / max(1, b - a)
        if sung:
            # Fold octave errors per frame before aggregating.
            # This prevents mixed-octave detections from producing
            # a median pitch between the two octave clusters.
            target_midi = float(note["midi"])
            frame_errors = np.asarray(
                fold_cents(np.asarray(sung, dtype=float) - target_midi),
                dtype=float,
            )
            cents = float(np.median(frame_errors))
            # Octave-normalized sung MIDI for downstream contour features.
            sung_med = target_midi + cents / 100.0
            voiced_js = [j for j in js if not np.isnan(usr[j])]
            onset_ms = (voiced_js[0] - a) * DTW_HOP * 1000.0
        else:
            sung_med, cents, onset_ms = None, None, None
        per_note.append({"index": idx, "lyric": note.get("lyric", ""), "start": note["start"],
                         "target_midi": note["midi"], "sung_midi": sung_med,
                         "cent_error": cents, "onset_ms": onset_ms, "coverage": coverage})

    sung_notes = [p for p in per_note if p["cent_error"] is not None and p["coverage"] >= 0.3]
    cents = np.array([abs(p["cent_error"]) for p in sung_notes]) if sung_notes else np.array([600.0])
'''
NEW_NOTE = '''        # Use the global shift estimated above, then fold octave errors
        # separately for each voiced frame BEFORE aggregating.
        voiced_js = [j for j in js if np.isfinite(usr_aligned[j])]
        sung = np.asarray([usr_aligned[j] for j in voiced_js], dtype=float)
        coverage = len(sung) / max(1, b - a)
        if len(sung):
            target_midi = float(note["midi"])
            frame_errors = np.asarray(fold_cents(sung - target_midi), dtype=float)
            cents = float(np.median(frame_errors))
            # Measure absolute frame errors before taking the median:
            # opposite-sign pitch errors must not cancel each other.
            abs_cents = float(np.median(np.abs(frame_errors)))
            sung_med = target_midi + cents / 100.0
            onset_ms = (voiced_js[0] - a) * DTW_HOP * 1000.0
        else:
            sung_med, cents, abs_cents, onset_ms = None, None, None, None
        per_note.append({"index": idx, "lyric": note.get("lyric", ""), "start": note["start"],
                         "target_midi": note["midi"], "sung_midi": sung_med,
                         "cent_error": cents, "abs_cent_error": abs_cents,
                         "onset_ms": onset_ms, "coverage": coverage})

    sung_notes = [p for p in per_note if p["abs_cent_error"] is not None and p["coverage"] >= 0.3]
    cents = np.array([p["abs_cent_error"] for p in sung_notes]) if sung_notes else np.array([600.0])
'''
OLD_INTERVAL = '''        ref_iv = q["target_midi"] - p["target_midi"]
        usr_iv = q["sung_midi"] - p["sung_midi"]
        interval_err.append(abs(usr_iv - ref_iv))
'''
NEW_INTERVAL = '''        ref_iv = q["target_midi"] - p["target_midi"]
        usr_iv = q["sung_midi"] - p["sung_midi"]
        interval_err.append(float(abs(fold_cents(usr_iv - ref_iv)) / 100.0))
'''


def verify_or_fix_features(allow_patch: bool) -> str:
    if not FEATURES_PY.is_file():
        raise FileNotFoundError(f'Missing: {FEATURES_PY}')
    source = FEATURES_PY.read_text(encoding='utf-8-sig')
    good = NEW_NOTE in source and NEW_INTERVAL in source
    if not good:
        if not allow_patch:
            raise RuntimeError('Offline fix not verified. Re-run with --fix-offline-octave.')
        if OLD_NOTE not in source or OLD_INTERVAL not in source:
            raise RuntimeError(
                'Current features.py differs from uploaded version; refusing automatic patch. '
                'Please provide current scoring/features.py.'
            )
        backup = FEATURES_PY.with_name('features.py.before_v3_octave.bak')
        if backup.exists() and backup.read_text(encoding='utf-8-sig') != source:
            raise RuntimeError(f'Existing backup differs; refusing overwrite: {backup}')
        if not backup.exists():
            backup.write_text(source, encoding='utf-8')
        source = source.replace(OLD_NOTE, NEW_NOTE, 1).replace(OLD_INTERVAL, NEW_INTERVAL, 1)
        FEATURES_PY.write_text(source, encoding='utf-8')
        print(f'[FIX] Per-note key shift, framewise octave folding and contour corrected. Backup: {backup}', flush=True)
    else:
        print('[CHECK] Per-note key shift and octave-aware metrics already present.', flush=True)
    from scoring.pitch_utils import fold_cents
    assert np.allclose(fold_cents(np.asarray([0., 12., -12.])), 0.)
    # Simulate note 60 with a singer shifted +2 semitones and octave artifact:
    # after key shift, all frames must match reference pitch.
    ref_note = 60.0
    detected = np.asarray([62., 74., 50.])
    shifted = detected - 2
    assert np.allclose(fold_cents(shifted - ref_note), 0.)
    # Signs must not cancel: +/- one semitone => median absolute is 100 cents.
    opposite_errors = fold_cents(np.asarray([61., 59.]) - ref_note)
    assert np.isclose(np.median(np.abs(opposite_errors)), 100.)
    assert NEW_NOTE in source and NEW_INTERVAL in source
    print('[PASS] Octave +12/-12, global +2 key shift, and absolute-error checks.', flush=True)
    return hashlib.sha256(source.encode('utf-8')).hexdigest()


def build_one_song(song_id, code_hash, force=False):
    from offline.compare_reference_singers import read_song, reference_from_audio
    from scoring.extract_dataset import audio_to_frames
    from scoring.features import extract_features, flatten

    records = read_song(song_id)
    if len(records) != 22 or set(records) != set(range(22)):
        raise RuntimeError(f'{song_id}: expected exactly singers 0..21; got {sorted(records)}')
    best = max(records, key=lambda sid: (records[sid]['overall'], -sid))
    fingerprint = hashlib.sha256(json.dumps({
        'song': song_id, 'best': best, 'score': records[best]['overall'],
        'code_hash': code_hash,
        'scores': {str(k): records[k]['overall'] for k in sorted(records)},
    }, sort_keys=True).encode('utf-8')).hexdigest()
    cache = EXPERIMENT_DIR / f'{song_id}_v3_top_reference.csv'
    meta = EXPERIMENT_DIR / f'{song_id}_v3_top_reference.meta.json'
    if not force and cache.exists() and meta.exists():
        info = json.loads(meta.read_text(encoding='utf-8'))
        if info.get('fingerprint') == fingerprint:
            df = pd.read_csv(cache, encoding='utf-8-sig')
            if len(df) == 22 and set(df['singer_id']) == set(range(22)):
                print(f'[{song_id}] Using verified cache (22 rows, reference Singer {best}).', flush=True)
                return df, best, records[best]['overall']
    print(f'[{song_id}] Reference Singer {best}, human label {records[best]["overall"]:.3f}', flush=True)
    reference = reference_from_audio(records[best])
    rows = []
    for i, sid in enumerate(sorted(records), 1):
        print(f'  [{song_id}] {i}/22 singer {sid}: extracting ...', flush=True)
        frames = audio_to_frames(records[sid]['audio'], records[sid]['sr'], 'pyin')
        values = flatten(extract_features(reference, frames, apply_key_shift=True))
        row = {'song': song_id, 'singer_id': sid, **values}
        rows.append(row)
    df = pd.DataFrame(rows).sort_values('singer_id')
    if len(df) != 22 or df[['song', 'singer_id']].duplicated().any():
        raise RuntimeError(f'{song_id}: duplicate or missing rows')
    # Save each complete song as a resumable checkpoint.
    tmp = cache.with_suffix('.csv.tmp')
    df.to_csv(tmp, index=False, encoding='utf-8-sig')
    tmp.replace(cache)
    meta.write_text(json.dumps({'fingerprint': fingerprint, 'reference_singer': best,
                                'reference_label': records[best]['overall'],
                                'feature_source_sha256': code_hash}, indent=2), encoding='utf-8')
    return df, best, records[best]['overall']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--fix-offline-octave', action='store_true',
                    help='Safely patch the exact reviewed scoring/features.py with backup')
    ap.add_argument('--force', action='store_true', help='Recompute cached songs')
    args = ap.parse_args()
    code_hash = verify_or_fix_features(args.fix_offline_octave)
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    dataframes, refs = [], []
    for n in range(1, 7):
        song = f'song{n}'
        df, ref, score = build_one_song(song, code_hash, args.force)
        dataframes.append(df)
        refs.append({'song': song, 'reference_singer_id': ref,
                     'reference_overall_performance': score,
                     'uses_test_song_labels': True})
    combined = pd.concat(dataframes, ignore_index=True)
    if len(combined) != 132 or combined[['song', 'singer_id']].duplicated().any():
        raise RuntimeError('Expected 132 unique (song, singer_id) rows; refusing export')
    if combined.select_dtypes(include=[np.number]).isna().any().any():
        raise RuntimeError('NaN detected in numeric features; refusing export')
    if not np.isfinite(combined.select_dtypes(include=[np.number]).to_numpy()).all():
        raise RuntimeError('Inf detected in numeric features; refusing export')
    # Retain original feature order for downstream train.py compatibility.
    baseline = OUT_DIR / 'features_v2.csv'
    if baseline.exists():
        expected = pd.read_csv(baseline, nrows=0, encoding='utf-8-sig').columns.tolist()
        missing = set(expected) - set(combined.columns)
        if missing:
            raise RuntimeError(f'Missing v2 columns: {sorted(missing)}')
        combined = combined[expected]
    out = OUT_DIR / 'features_v3_experimental.csv'
    combined.to_csv(out, index=False, encoding='utf-8-sig')
    ref_out = EXPERIMENT_DIR / 'v3_reference_selection.csv'
    pd.DataFrame(refs).to_csv(ref_out, index=False, encoding='utf-8-sig')
    report = EXPERIMENT_DIR / 'v3_README.txt'
    report.write_text(
        'EXPLORATORY FEATURES V3; NOT VALID FOR LEAK-FREE LOSO.\n'
        'References were selected using each TEST SONG\'S human overall_performance labels.\n'
        'Dropping the reference singer row does NOT remove this information leakage.\n'
        'The same 22 singers per song are included; reference singers have self-match bias.\n'
        'For training, do not treat the resulting LOSO as an unbiased evaluation.\n'
        'Feature algorithm includes per-voiced-frame octave folding before median,\n'
        'applied key_shift and octave-aware contour interval metric.\n'
        f'Feature source SHA256: {code_hash}\n'
        f'Features: {out}\nReference choices: {ref_out}\n', encoding='utf-8')
    print('\nSUCCESS: 132 unique rows, 6 songs x 22 singers.', flush=True)
    print('Features:', out)
    print('References:', ref_out)
    print('Readme:', report)
    print('IMPORTANT: Label-informed exploratory v3, NOT leak-free LOSO.', flush=True)

if __name__ == '__main__':
    main()
