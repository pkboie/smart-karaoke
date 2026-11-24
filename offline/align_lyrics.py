
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SONG_DIR = ROOT / "data" / "songs" / "song6"

song_path = SONG_DIR / "song.json"
lyrics_path = SONG_DIR / "lyrics_timing.json"

song = json.loads(song_path.read_text(encoding="utf-8"))
lyrics = json.loads(lyrics_path.read_text(encoding="utf-8"))

# Back up the current reference
backup = SONG_DIR / "song_before_alignment.json"
if not backup.exists():
    shutil.copy2(song_path, backup)

# Clear previous lyric assignments
for note in song["notes"]:
    note["lyric"] = ""

for line in lyrics["lines"]:
    start = line["start"]
    end = line["end"]
    chars = list(line["text"].replace(" ", ""))

    candidates = [
        note for note in song["notes"]
        if start <= (note["start"] + note["end"]) / 2 < end
    ]

    if not candidates or not chars:
        print("Skipped:", start, end)
        continue

    # Divide the phrase into equal time intervals.
    # Assign each character to its closest note.
    for i, char in enumerate(chars):
        target_time = start + (i + 0.5) * (end - start) / len(chars)
        note = min(
            candidates,
            key=lambda n: abs((n["start"] + n["end"]) / 2 - target_time)
        )
        note["lyric"] += char

song_path.write_text(
    json.dumps(song, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

assigned = sum(bool(n["lyric"]) for n in song["notes"])

print("Song:", song["title"])
print("Lines:", len(lyrics["lines"]))
print("Notes with lyrics:", assigned)
print("Backup:", backup)
