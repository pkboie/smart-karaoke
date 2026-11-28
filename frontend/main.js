// Smart Karaoke 前端（負責人：#4 畫面、#6 即時判分、#1 收音、#2 延遲）
// 即時音高偵測在瀏覽器裡做（pitchy），唱完把 trace 送到後端評分。
// pitchy 4.1.0 已打包在 vendor/，現場 demo 沒有網路也能用
import { PitchDetector } from "./vendor/pitchy.js";
import { foldCents, inJudgeWindow, judgeNote } from "./note-judge.js";
import { measureLoopbackLatency } from "./latency-calibration.js?v=v1safe";

const $ = (id) => document.getElementById(id);
const audio = $("audio");
const canvas = $("canvas");
const ctx = canvas.getContext("2d");

const VIEW_SEC = 6;          // 畫面寬度代表幾秒
const NOW_X = 0.25;          // 「現在」線在畫面的位置（比例）
const CLARITY_MIN = 0.85;    // pitchy 的 clarity 門檻
const RMS_MIN = 0.01;        // 低於這個音量視為沒在唱（簡易 VAD，#1 可改進）
const NOISE_MULTIPLIER = 3;     // Threshold = noise RMS * 3
const RMS_MAX = 0.05;           // Maximum adaptive threshold
const CALIBRATION_MS = 1000;    // Measure background noise for 1 second

let song = null, songId = null;
let frames = [];             // 送給後端的 trace
let noteStats = [];          // 每個音符：判斷窗內有聲格的 MIDI、唱完後的判定結果
let micCtx = null;
let analyser = null;
let detector = null;
let stream = null;

let micSource = null;
let micWorklet = null;

// H/G: The accompaniment and captured microphone frames share this AudioContext clock.
let songSource = null;
let songStartCtxTime = null;
let songBufferDuration = 0;
const currentSongTime = () => (micCtx && songStartCtxTime !== null)
  ? Math.max(0, micCtx.currentTime - songStartCtxTime)
  : 0;


let running = false;
let rmsThreshold = RMS_MIN;
let backgroundRms = 0;

let pitchTolerance = 100;
const HOP_SAMPLES = 1024;    // 和 mic-processor.js 的 hopSize 相同：每 1024 樣本送一格
let hopSec = HOP_SAMPLES / 48000;   // 開麥克風後依實際取樣率更新

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
  // result：undefined = 還沒唱完；null = 唱完但沒有格子（未判定）；{centError, hit} = 已判定
  noteStats = song.notes.map(() => ({ midis: [], result: undefined }));
}
$("song").onchange = (e) => loadSong(e.target.value);

// ---------- 音高 ----------
const hzToMidi = (hz) => 69 + 12 * Math.log2(hz / 440);
const latencySec = () => Number($("latency").value) / 1000;
// H: Beep loopback is an approximate acoustic estimate, NOT a guaranteed mic-only offset.
$("calibrate-latency").onclick = async () => {
  const button = $("calibrate-latency");
  const status = $("latency-status");
  if (running) return;
  button.disabled = true;
  try {
    const measurement = await measureLoopbackLatency((message) => {
      status.textContent = message;
    });

    const all = measurement.samplesMs.map(v => v.toFixed(1)).join(", ");
    const used = measurement.validSamplesMs.map(v => v.toFixed(1)).join(", ");

    if (measurement.reliable) {
      $("latency").value = measurement.medianMs.toFixed(1);

      status.textContent =
      `聲學回錄粗估 ${measurement.medianMs.toFixed(1)} ms` +
      `（原始 ${all}；採用 ${used}）` +
      `；波動較小，已填入。`;
    } else {
    status.textContent =
      `聲學回錄初測 ${measurement.medianMs.toFixed(1)} ms` +
      `（原始 ${all}；採用 ${used}）` +
      `；結果不穩定，未自動套用。`;
    }
  } catch (error) {
    console.error(error);
    status.textContent = `校正失敗：${error.message}`;
  } finally {
    button.disabled = false;
  }
};

const midiRange = () => {
  const ms = song.notes.map((n) => n.midi);
  return [Math.min(...ms) - 3, Math.max(...ms) + 3];
};


async function startMic() {
  stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false
    }
  });

  micCtx = new AudioContext();
  await micCtx.resume();
  hopSec = HOP_SAMPLES / micCtx.sampleRate;

  // Keep analyser for background noise calibration.
  analyser = micCtx.createAnalyser();
  analyser.fftSize = 2048;

  micSource = micCtx.createMediaStreamSource(stream);
  micSource.connect(analyser);

  // Pitch detector uses 2048-sample frames.
  detector = PitchDetector.forFloat32Array(2048);
}


async function setupAudioWorklet() {
  await micCtx.audioWorklet.addModule(
    new URL("./mic-processor.js", import.meta.url)
  );

  micWorklet = new AudioWorkletNode(
    micCtx,
    "mic-processor",
    {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      outputChannelCount: [1]
    }
  );

  // Audio frames will be received here.
  micWorklet.port.onmessage = (event) => {
    if (!running) return;

    // Timestamp is generated by AudioWorklet on the audio rendering thread.
    processAudioFrame(event.data);
  };

  micSource.connect(micWorklet);

  // The processor outputs silence, preventing feedback.
  micWorklet.connect(micCtx.destination);
}


async function calibrateNoise() {
  const calibrationBuffer = new Float32Array(analyser.fftSize);
  const rmsValues = [];

  const intervalMs = 50;
  const sampleCount = CALIBRATION_MS / intervalMs;

  // Collect background audio for approximately 1 second
  for (let i = 0; i < sampleCount; i++) {
    analyser.getFloatTimeDomainData(calibrationBuffer);

    let sum = 0;

    for (const value of calibrationBuffer) {
      sum += value * value;
    }

    const rms = Math.sqrt(sum / calibrationBuffer.length);
    rmsValues.push(rms);

    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  // Calculate average background RMS
  backgroundRms =
    rmsValues.reduce((sum, value) => sum + value, 0) /
    rmsValues.length;

  // Set adaptive threshold
  rmsThreshold = Math.max(
    RMS_MIN,
    Math.min(RMS_MAX, backgroundRms * NOISE_MULTIPLIER)
  );

  console.log("Background RMS:", backgroundRms);
  console.log("Adaptive RMS threshold:", rmsThreshold);
}


// G: Play the reference track with AudioBufferSourceNode in micCtx.
// Both the song start and the Worklet frame timestamps now share one clock.
async function startAccompaniment() {
  const startDelaySec = 0.15;
  songBufferDuration = Number(song?.duration) || 0;

  if (song?.accompaniment) {
    const response = await fetch(audio.src);
    if (!response.ok) throw new Error("無法取得伴奏音檔。");
    const bytes = await response.arrayBuffer();
    const buffer = await micCtx.decodeAudioData(bytes);
    songBufferDuration = buffer.duration;

    songSource = micCtx.createBufferSource();
    songSource.buffer = buffer;
    songSource.connect(micCtx.destination);
  }

  songStartCtxTime = micCtx.currentTime + startDelaySec;
  if (songSource) {
    songSource.onended = () => { if (running) finish(); };
    songSource.start(songStartCtxTime);
  }
}

function stopMic() {
  if (songSource) {
    songSource.onended = null;
    try { songSource.stop(); } catch { /* already stopped */ }
    songSource.disconnect();
    songSource = null;
  }
  songStartCtxTime = null;
  songBufferDuration = 0;

  if (micWorklet) {
    micWorklet.port.onmessage = null;
    micWorklet.disconnect();
  }

  if (micSource) {
    micSource.disconnect();
  }

  stream?.getTracks().forEach(track => track.stop());

  if (micCtx && micCtx.state !== "closed") {
    micCtx.close();
  }

  micWorklet = null;
  micSource = null;
  analyser = null;
  detector = null;
  stream = null;
  micCtx = null;
}



function processAudioFrame(packet) {
  if (!running || !micCtx || !detector || songStartCtxTime === null) {
    return;
  }

  const { frame: audioFrame, contextTime } = packet;
  if (!(audioFrame instanceof Float32Array) || !Number.isFinite(contextTime)) return;
  // Window-center acquisition time, not delayed message-handling time.
  const t = contextTime - songStartCtxTime - latencySec();
  if (t < 0 || (songBufferDuration > 0 && t > songBufferDuration)) return;

  // Calculate RMS
  let sum = 0;

  for (const value of audioFrame) {
    sum += value * value;
  }

  const rms = Math.sqrt(sum / audioFrame.length);

  // Detect pitch using pitchy
  const [hz, clarity] = detector.findPitch(
    audioFrame,
    micCtx.sampleRate
  );

  // Adaptive RMS VAD
  const voiced =
    rms > rmsThreshold &&
    clarity > CLARITY_MIN &&
    hz > 60 &&
    hz < 1100;

  const midi = voiced ? hzToMidi(hz) : null;

  // Save data for backend scoring
  frames.push({
    t,
    f0_hz: voiced ? hz : null,
    midi,
    voiced,
    rms
  });

  // 逐音符判分：先收集判斷窗內（跳過開頭滑音）的有聲格，音符唱完再由 noteResult() 取中位數判定
  const idx = song.notes.findIndex((n) => inJudgeWindow(t, n));
  if (idx >= 0 && voiced) noteStats[idx].midis.push(midi);
}

// 第 i 個音符的判定結果。唱完（扣掉延遲後的時間過了 end）才判定一次並記下來；
// 用 t 而不是 audio.currentTime 判斷「唱完」，否則延遲期間還在送進來的格子會被漏掉
function noteResult(i) {
  const st = noteStats[i], n = song.notes[i];
  if (st.result === undefined && currentSongTime() - latencySec() >= n.end) {
    st.result = judgeNote(st.midis, n.midi, pitchTolerance, (n.end - n.start) / hopSec);
  }
  return st.result;
}

// ---------- 畫面 ----------
function draw() {
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (!song) return;
  const now = currentSongTime();
  const [lo, hi] = midiRange();
  const pxPerSec = W / VIEW_SEC;
  const x = (t) => W * NOW_X + (t - now) * pxPerSec;
  const y = (m) => H - ((m - lo) / (hi - lo)) * H;
  const noteH = H / (hi - lo) * 0.8;

  // 目標音符
  song.notes.forEach((n, i) => {
    const x0 = x(n.start), x1 = x(n.end);
    if (x1 < 0 || x0 > W) return;
    const r = noteResult(i);
    ctx.fillStyle = r ? (r.hit ? "#3ecf9a" : "#f0a35e") : "#4f7dd9";
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
  $("bar").style.width = `${(100 * now) / (songBufferDuration || song.duration || 1)}%`;
  // 即時命中率 = 已判定的音符中命中幾個（和結果頁一樣以音符為單位）
  const judged = song.notes.map((_, i) => noteResult(i)).filter((r) => r);
  const hits = judged.filter((r) => r.hit).length;
  $("live").textContent = `即時命中率 ${judged.length ? Math.round((100 * hits) / judged.length) : 0}%`;
}

function loop() {
  if (!running) return;

  draw();
  if (!songSource && songBufferDuration > 0 && currentSongTime() >= songBufferDuration) {
    finish();
    return;
  }
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

  $("start").disabled = true;
  $("calibrate-latency").disabled = true;

  try {
    if (!song) {
      throw new Error(
        "歌曲還沒載入，請先執行 python offline/make_demo_song.py。"
      );
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error(
        "無法使用麥克風，請透過 http://localhost:8000 開啟。"
      );
    }

    pitchTolerance = Number($("difficulty").querySelector("input:checked").value);
    $("song").disabled = true;
    $("difficulty").disabled = true;

    // Step 1: Start microphone
    msg.textContent = "正在要求麥克風權限…";
    await startMic();

    // Step 2: Calibrate background noise
    msg.textContent = "正在校正環境噪音，請保持安靜 1 秒…";
    await calibrateNoise();

    // Step 3: Set up AudioWorklet
    msg.textContent = "正在初始化音訊處理…";
    await setupAudioWorklet();

    // Step 4: Reset previous recording
    resetStats();
    $("result").hidden = true;

    // Step 5: Schedule accompaniment on the mic AudioContext timeline.
    msg.textContent = "正在載入伴奏與同步音訊時鐘…";
    await startAccompaniment();

    // Step 6: Start pitch detection and drawing
    running = true;
    $("stop").disabled = false;
    msg.textContent = "";

    loop();

  } catch (e) {
    console.error(e);

    running = false;
    stopMic();

    $("start").disabled = false;
    $("stop").disabled = true;
    $("calibrate-latency").disabled = false;

    $("song").disabled = false;
    $("difficulty").disabled = false;
    $("start").disabled = !song;
    msg.textContent =
      MIC_ERRORS[e.name] ||
      `無法開始：${e.message || e.name}`;
  }
};


window.addEventListener("error", (e) => { $("msg").textContent = `程式錯誤：${e.message}`; });
window.addEventListener("unhandledrejection", (e) => { $("msg").textContent = `程式錯誤：${e.reason?.message || e.reason}`; });
$("stop").onclick = () => finish();

async function finish() {
  if (!running) return;
  running = false;
  stopMic();
  $("stop").disabled = true;
  $("calibrate-latency").disabled = false;
  const tolerance = pitchTolerance;
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
  $("note-counts").textContent = `±${tolerance} cent · 命中 ${hits} · 偏離 ${misses} · 未判定 ${notes.length - hits - misses}`;
  $("note-summary").hidden = !notes.length;
}

loadSongs();
