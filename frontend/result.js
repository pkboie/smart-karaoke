import { RESULT_KEY } from "./song-flow.js";

const $ = (id) => document.getElementById(id);

function renderNotes(notes, tolerance) {
  let hits = 0;
  let misses = 0;
  const items = notes.map((note) => {
    const item = document.createElement("li");
    const lyric = document.createElement("strong");
    const status = document.createElement("span");
    const time = document.createElement("span");
    lyric.textContent = note.lyric || `第 ${note.index + 1} 音`;
    status.className = "note-status";
    time.className = "note-time";
    time.textContent = `${note.start.toFixed(1)} 秒`;
    if (note.cent_error == null || note.coverage < 0.3) {
      status.textContent = "未判定";
    } else if (Math.abs(note.cent_error) < tolerance) {
      status.textContent = "命中";
      item.className = "note-hit";
      hits += 1;
    } else {
      const direction = note.cent_error > 0 ? "偏高" : "偏低";
      status.textContent = `${direction} ${Math.round(Math.abs(note.cent_error))} cent`;
      item.className = "note-miss";
      misses += 1;
    }
    item.append(lyric, status, time);
    return item;
  });
  $("note-results").replaceChildren(...items);
  $("note-counts").textContent = `±${tolerance} cent · 命中 ${hits} · 偏離 ${misses} · 未判定 ${notes.length - hits - misses}`;
  $("note-summary").hidden = !notes.length;
}

function loadResult() {
  try {
    return JSON.parse(sessionStorage.getItem(RESULT_KEY));
  } catch {
    return null;
  }
}

const saved = loadResult();
if (saved?.songId && saved.result) {
  const { songId, title, tolerance, latency, result } = saved;
  $("result-song").textContent = title || songId;
  $("retry").href = `./?${new URLSearchParams({ difficulty: tolerance, latency })}`;

  for (const key of ["overall", "pitch", "rhythm", "contour", "expression"]) {
    $(`s-${key}`).textContent = result[key];
    $(`m-${key}`).value = result[key];
  }
  const tips = result.tips.map((tip) => {
    const item = document.createElement("li");
    item.textContent = tip;
    return item;
  });
  $("tips").replaceChildren(...tips);
  renderNotes(result.per_note ?? [], tolerance);
  $("result").hidden = false;
} else {
  $("result-status").hidden = false;
}
