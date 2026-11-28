import { RESULT_KEY } from "./song-flow.js";

const $ = (id) => document.getElementById(id);

const RADAR_AXES = [
  { key: "pitch", x: 0, y: -1 },
  { key: "rhythm", x: 1, y: 0 },
  { key: "contour", x: 0, y: 1 },
  { key: "expression", x: -1, y: 0 },
];

function drawRadar(values) {
  const canvas = $("score-radar");
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const center = canvas.width / 2;
  const radius = center - 12;
  const palette = getComputedStyle(canvas);
  const pointsAt = (scales) => RADAR_AXES.map(({ x, y }, i) => [
    center + x * radius * scales[i],
    center + y * radius * scales[i],
  ]);

  function tracePolygon(points) {
    ctx.beginPath();
    ctx.moveTo(...points[0]);
    for (const point of points.slice(1)) ctx.lineTo(...point);
    ctx.closePath();
  }

  ctx.lineJoin = "round";
  ctx.lineWidth = 2;
  ctx.strokeStyle = palette.getPropertyValue("--radar-grid").trim();
  for (const scale of [0.25, 0.5, 0.75, 1]) {
    tracePolygon(pointsAt(RADAR_AXES.map(() => scale)));
    ctx.stroke();
  }
  ctx.beginPath();
  ctx.moveTo(center, center - radius);
  ctx.lineTo(center, center + radius);
  ctx.moveTo(center - radius, center);
  ctx.lineTo(center + radius, center);
  ctx.stroke();

  const points = pointsAt(values);
  tracePolygon(points);
  ctx.fillStyle = palette.getPropertyValue("--radar-fill").trim();
  ctx.fill();
  ctx.strokeStyle = palette.getPropertyValue("--radar-outline").trim();
  ctx.lineWidth = 4;
  ctx.stroke();

  ctx.fillStyle = palette.getPropertyValue("--radar-marker").trim();
  for (const [x, y] of points) {
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, 2 * Math.PI);
    ctx.fill();
  }
}

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

  $("s-overall").textContent = result.overall;
  $("m-overall").value = result.overall;
  const radarValues = RADAR_AXES.map(({ key }) => {
    const score = result[key];
    $(`s-${key}`).textContent = score ?? "-";
    return Number.isFinite(score) ? Math.min(100, Math.max(0, score)) / 100 : 0;
  });
  drawRadar(radarValues);
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
