// Smart Karaoke 前端（負責人：#4 畫面、#6 即時判分、#1 收音、#2 延遲）
// 即時音高偵測在瀏覽器裡做（pitchy），唱完把 trace 送到後端評分。
// pitchy 4.1.0 已打包在 vendor/，現場 demo 沒有網路也能用
import { PitchDetector } from "./vendor/pitchy.js";

const $ = (id) => document.getElementById(id);
const audio = $("audio");
const canvas = $("canvas");
const ctx = canvas.getContext("2d");

const VIEW_SEC = 6;          // 畫面寬度代表幾秒
const NOW_X = 0.25;          // 「現在」線在畫面的位置（比例）
const CLARITY_MIN = 0.85;    // pitchy 的 clarity 門檻
const RMS_MIN = 0.01;        // 低於這個音量視為沒在唱（簡易 VAD，#1 可改進）

let song = null, songId = null;
let frames = [];             // 送給後端的 trace
let noteStats = [];          // 每個音符：唱到幾格、命中幾格
let micCtx = null, analyser = null, detector = null, buf = null, stream = null;
let running = false;

// ---------- 載入歌曲 ----------
async function loadSongs() {
  const selector = $("song");
  try {
    const response = await fetch("/api/songs");
    if (!response.ok) throw new Error("目前無法讀取歌曲清單，請重新整理後再試。");
    const list = await response.json();
    if (!list.length) {
      selector.replaceChildren(new Option("沒有可唱的歌曲", ""));
      $("msg").textContent = "加入歌曲後重新整理，或先執行 python offline/make_demo_song.py 建立小星星。";
      return;
    }
    selector.replaceChildren(...list.map(({ id, title }) => new Option(title, id)));
    await loadSong(selector.value);
  } catch (error) {
    selector.replaceChildren(new Option("無法載入歌曲", ""));
    $("msg").textContent = error.message;
  }
}
async function loadSong(id) {
  $("song").disabled = true;
  $("start").disabled = true;
  $("result").hidden = true;
  $("lyric").textContent = "—";
  $("next-lyric").hidden = true;
  $("live").textContent = "即時命中率 0%";
  $("bar").style.width = "0%";
  $("msg").textContent = "正在載入歌曲…";
  song = null;
  songId = null;
  audio.removeAttribute("src");
  audio.load();
  draw();

  try {
    const base = `/songs/${encodeURIComponent(id)}/`;
    const response = await fetch(`${base}song.json`);
    if (!response.ok) throw new Error("無法載入這首歌的音準與歌詞資料。");
    const selected = await response.json();
    if (!selected.notes?.length) throw new Error("這首歌還沒有可用的音符資料。");
    song = selected;
    songId = id;
    if (selected.accompaniment) audio.src = base + selected.accompaniment;
    resetStats();
    draw();
    $("msg").textContent = "";
  } catch (error) {
    $("msg").textContent = error.message;
  } finally {
    $("song").disabled = false;
    $("start").disabled = !song;
  }
}
function resetStats() {
  frames = [];
  noteStats = song.notes.map(() => ({ voiced: 0, hit: 0 }));
}
$("song").onchange = (e) => loadSong(e.target.value);

// ---------- 音高 ----------
const hzToMidi = (hz) => 69 + 12 * Math.log2(hz / 440);
const foldCents = (d) => ((((d * 100) % 1200) + 1800) % 1200) - 600;  // 忽略八度
const midiRange = () => {
  const ms = song.notes.map((n) => n.midi);
  return [Math.min(...ms) - 3, Math.max(...ms) + 3];
};

async function startMic() {
  stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
  });
  micCtx = new AudioContext();
  analyser = micCtx.createAnalyser();
  analyser.fftSize = 2048;
  micCtx.createMediaStreamSource(stream).connect(analyser);
  detector = PitchDetector.forFloat32Array(analyser.fftSize);
  buf = new Float32Array(detector.inputLength);
}
function stopMic() {
  stream?.getTracks().forEach((t) => t.stop());
  if (micCtx && micCtx.state !== "closed") micCtx.close();
  stream = null;
  micCtx = null;
}

function sample() {
  analyser.getFloatTimeDomainData(buf);
  let sum = 0;
  for (const v of buf) sum += v * v;
  const rms = Math.sqrt(sum / buf.length);
  const [hz, clarity] = detector.findPitch(buf, micCtx.sampleRate);
  const voiced = rms > RMS_MIN && clarity > CLARITY_MIN && hz > 60 && hz < 1100;
  const latency = Number($("latency").value) / 1000;
  const t = audio.currentTime - latency;
  const midi = voiced ? hzToMidi(hz) : null;
  frames.push({ t, f0_hz: voiced ? hz : null, midi, voiced, rms });

  // 逐音符即時判分
  const tol = Number($("difficulty").value);
  const idx = song.notes.findIndex((n) => t >= n.start && t < n.end);
  if (idx >= 0 && voiced) {
    noteStats[idx].voiced++;
    if (Math.abs(foldCents(midi - song.notes[idx].midi)) < tol) noteStats[idx].hit++;
  }
}

// ---------- 畫面 ----------
function draw() {
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (!song) return;
  const now = audio.currentTime;
  const [lo, hi] = midiRange();
  const pxPerSec = W / VIEW_SEC;
  const x = (t) => W * NOW_X + (t - now) * pxPerSec;
  const y = (m) => H - ((m - lo) / (hi - lo)) * H;
  const noteH = H / (hi - lo) * 0.8;

  // 目標音符
  song.notes.forEach((n, i) => {
    const x0 = x(n.start), x1 = x(n.end);
    if (x1 < 0 || x0 > W) return;
    const st = noteStats[i];
    const done = n.end < now;
    ctx.fillStyle = done && st.voiced ? (st.hit / st.voiced > 0.5 ? "#3ecf9a" : "#f0a35e") : "#4f7dd9";
    ctx.globalAlpha = 0.85;
    ctx.fillRect(x0, y(n.midi) - noteH / 2, x1 - x0, noteH);
  });
  ctx.globalAlpha = 1;

  // 使用者的音高軌跡（折回到目標音附近，方便男女生對照）
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 3;
  ctx.beginPath();
  let pen = false;
  for (const f of frames) {
    const fx = x(f.t);
    if (fx < 0 || !f.voiced) { pen = false; continue; }
    const target = song.notes.find((n) => f.t >= n.start && f.t < n.end)?.midi ?? (lo + hi) / 2;
    const shown = target + foldCents(f.midi - target) / 100;
    if (pen) ctx.lineTo(fx, y(shown)); else ctx.moveTo(fx, y(shown));
    pen = true;
  }
  ctx.stroke();

  // 「現在」線
  ctx.fillStyle = "#f0a35e";
  ctx.fillRect(W * NOW_X - 1, 0, 2, H);

  // 歌詞、進度、即時命中率
  const cur = song.notes.find((n) => n.lyric && now >= n.start && now < n.end);
  const next = song.notes.filter((n) => n.lyric && n.start > now).slice(0, 6).map((n) => n.lyric).join("");
  $("lyric").textContent = cur?.lyric || "—";
  $("next-lyric").textContent = next ? `接下來 ${next}` : "";
  $("next-lyric").hidden = !next;
  $("bar").style.width = `${(100 * now) / (audio.duration || song.duration || 1)}%`;
  const v = noteStats.reduce((a, s) => a + s.voiced, 0);
  const h = noteStats.reduce((a, s) => a + s.hit, 0);
  $("live").textContent = `即時命中率 ${v ? Math.round((100 * h) / v) : 0}%`;
}

function loop() {
  if (!running) return;
  sample();
  draw();
  requestAnimationFrame(loop);
}

// ---------- 開始 / 結束 ----------
const MIC_ERRORS = {
  NotAllowedError: "麥克風權限被拒絕：請點網址列左邊的圖示，把麥克風改成「允許」後重新整理。也請確認 Windows 設定 > 隱私權與安全性 > 麥克風 已開啟。",
  NotFoundError: "找不到麥克風：請接上麥克風或耳機麥克風，並確認 Windows 的聲音設定裡有輸入裝置。",
  NotReadableError: "麥克風被其他程式佔用或無法啟動：請關閉視訊會議等正在用麥克風的程式後再試。",
};
$("start").onclick = async () => {
  const msg = $("msg");
  try {
    if (!song) throw new Error("歌曲還沒載入，請確認選單裡有歌曲（沒有的話先執行 python offline/make_demo_song.py）。");
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("這個網址不能使用麥克風，請改用 http://localhost:8000 開啟。");
    $("song").disabled = true;
    $("difficulty").disabled = true;
    $("start").disabled = true;
    msg.textContent = "正在要求麥克風權限…（瀏覽器若跳出詢問，請按「允許」）";
    await startMic();
    resetStats();
    $("result").hidden = true;
    audio.currentTime = 0;
    if (song.accompaniment) await audio.play();
    msg.textContent = "";
    running = true;
    $("stop").disabled = false;
    loop();
  } catch (e) {
    console.error(e);
    stopMic();
    $("song").disabled = false;
    $("difficulty").disabled = false;
    $("start").disabled = !song;
    msg.textContent = MIC_ERRORS[e.name] || `無法開始：${e.message || e.name}`;
  }
};
window.addEventListener("error", (e) => { $("msg").textContent = `程式錯誤：${e.message}`; });
window.addEventListener("unhandledrejection", (e) => { $("msg").textContent = `程式錯誤：${e.reason?.message || e.reason}`; });
$("stop").onclick = () => finish();
audio.onended = () => finish();

async function finish() {
  if (!running) return;
  running = false;
  audio.pause();
  stopMic();
  $("stop").disabled = true;
  const tolerance = Number($("difficulty").value);
  $("msg").textContent = "正在評分…";
  try {
    const response = await fetch("/api/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        song: songId,
        offset_ms: 0,
        strict: tolerance === 50,
        frames,
        label: $("trace-label").value.trim() || undefined,
      }),
    });
    if (!response.ok) throw new Error("評分失敗，請重新唱一次。");
    renderResult(await response.json(), tolerance);
    $("msg").textContent = "";
  } catch (error) {
    $("msg").textContent = error.message;
  } finally {
    $("song").disabled = false;
    $("difficulty").disabled = false;
    $("start").disabled = false;
  }
}

function renderResult(result, tolerance) {
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
  $("result-heading").focus();
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
  $("note-counts").textContent = `命中 ${hits} · 偏離 ${misses} · 未判定 ${notes.length - hits - misses}`;
  $("note-summary").hidden = !notes.length;
}

loadSongs();
