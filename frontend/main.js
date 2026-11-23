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
const NOISE_MULTIPLIER = 3;     // Threshold = noise RMS * 3
const RMS_MAX = 0.05;           // Maximum adaptive threshold
const CALIBRATION_MS = 1000;    // Measure background noise for 1 second

let song = null, songId = null;
let frames = [];             // 送給後端的 trace
let noteStats = [];          // 每個音符：唱到幾格、命中幾格
let micCtx = null;
let analyser = null;
let detector = null;
let stream = null;

let micSource = null;
let micWorklet = null;

let running = false;
let rmsThreshold = RMS_MIN;
let backgroundRms = 0;

let audioFrameCount = 0;

// ---------- 載入歌曲 ----------
async function loadSongs() {
  const list = await (await fetch("/api/songs")).json();
  $("song").innerHTML = list.map((s) => `<option value="${s.id}">${s.title}</option>`).join("");
  await loadSong(list[0]?.id);
}
async function loadSong(id) {
  if (!id) return;
  songId = id;
  song = await (await fetch(`/songs/${id}/song.json`)).json();
  audio.src = song.accompaniment ? `/songs/${id}/${song.accompaniment}` : "";
  resetStats();
  draw();
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
    audio: {
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false
    }
  });

  micCtx = new AudioContext();
  await micCtx.resume();

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

    const audioFrame = event.data;

    // This function will be added in the next step.
    processAudioFrame(audioFrame);
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


function stopMic() {
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



function processAudioFrame(audioFrame) {
  if (!running || !micCtx || !detector) {
    return;
  }

  audioFrameCount++;

  if (audioFrameCount % 50 === 0) {
    console.log("Audio frames processed:", audioFrameCount);
  }

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

  // Keep existing latency calculation
  const latency = Number($("latency").value) / 1000;
  const t = audio.currentTime - latency;

  const midi = voiced ? hzToMidi(hz) : null;

  // Save data for backend scoring
  frames.push({
    t,
    f0_hz: voiced ? hz : null,
    midi,
    voiced,
    rms
  });

  // Real-time note judging
  const tol = Number($("difficulty").value);

  const idx = song.notes.findIndex(
    (n) => t >= n.start && t < n.end
  );

  if (idx >= 0 && voiced) {
    noteStats[idx].voiced++;

    if (
      Math.abs(
        foldCents(midi - song.notes[idx].midi)
      ) < tol
    ) {
      noteStats[idx].hit++;
    }
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
  const cur = song.notes.find((n) => now >= n.start - 0.3 && now < n.end);
  $("lyric").textContent = cur?.lyric || "—";
  $("bar").style.width = `${(100 * now) / (audio.duration || song.duration || 1)}%`;
  const v = noteStats.reduce((a, s) => a + s.voiced, 0);
  const h = noteStats.reduce((a, s) => a + s.hit, 0);
  $("live").textContent = `即時命中率 ${v ? Math.round((100 * h) / v) : 0}%`;
}

function loop() {
  if (!running) return;

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

  $("start").disabled = true;

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
    audio.currentTime = 0;

    // Step 5: Start accompaniment
    if (song.accompaniment) {
      await audio.play();
    }

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

    msg.textContent =
      MIC_ERRORS[e.name] ||
      `無法開始：${e.message || e.name}`;
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
  $("start").disabled = false;
  $("stop").disabled = true;
  const res = await fetch("/api/score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ song: songId, offset_ms: 0, strict: $("difficulty").value === "50", frames }),
  });
  const s = await res.json();
  for (const k of ["overall", "pitch", "rhythm", "contour", "expression"]) $(`s-${k}`).textContent = s[k];
  $("tips").innerHTML = s.tips.map((t) => `<li>${t}</li>`).join("");
  $("result").hidden = false;
}

loadSongs();
