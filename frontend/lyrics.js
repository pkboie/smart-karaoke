function linesFromNotes(notes, bpm) {
  const beat = Number.isFinite(bpm) && bpm > 0 ? 60 / bpm : 0.6;
  const sungNotes = notes
    .filter((note) => typeof note.lyric === "string" && note.lyric.trim())
    .sort((a, b) => a.start - b.start);
  const lines = [];
  let line = null;

  for (const note of sungNotes) {
    if (!line || note.start - line.end >= beat) {
      line = { start: note.start, end: note.end, text: "" };
      lines.push(line);
    }
    line.end = Math.max(line.end, note.end);
    line.text += note.lyric;

    // With only note-level lyrics, use pauses, punctuation and phrase-ending held notes.
    const length = Array.from(line.text.trim()).length;
    const heldNote = note.end - note.start >= 1.6 * beat;
    if (/[。！？!?]$/.test(note.lyric.trim()) || (length >= 4 && heldNote) || length >= 16) {
      line = null;
    }
  }

  return lines;
}

export async function loadLyricLines(base, song) {
  try {
    const response = await fetch(`${base}lyrics_timing.json`);
    if (response.ok) {
      const { lines } = await response.json();
      if (Array.isArray(lines)) {
        const timedLines = lines
          .filter((line) => line && Number.isFinite(line.start) && Number.isFinite(line.end) &&
            line.end > line.start && typeof line.text === "string" && line.text.trim())
          .sort((a, b) => a.start - b.start);
        if (timedLines.length) return timedLines;
      }
    }
  } catch {
    // Timed lyrics are optional; the melody can still provide phrase cues.
  }

  return linesFromNotes(song.notes, song.bpm);
}

export function lyricsAt(lines, time) {
  const upcoming = lines.findIndex((line) => line.start > time);
  const next = lines[upcoming];
  const previous = lines[(upcoming < 0 ? lines.length : upcoming) - 1];
  const shortPause = previous && next && next.start - previous.end <= 1.25;

  return {
    current: previous && (time < previous.end || shortPause) ? previous.text.trim() : "",
    next: next?.text.trim() ?? "",
  };
}
