// 用 Node 跑前端實際使用的 pitchy（McLeod 演算法），讓 E1 能和 YIN／pYIN 一起比較。
// 負責人：#6
//
// 用法（通常由 pitch_benchmark.py 呼叫，不用手動執行）：
//   node experiments/pitchy_f0.mjs <取樣率>  < 音訊.f32
// 輸入（stdin）：單聲道 float32 little-endian 原始樣本
// 輸出（stdout）：JSON {"hop_sec": 0.01, "f0": [hz 或 null, ...]}，第 k 筆在 k * hop_sec 秒（與 detect_pitch 相同）
//
// 參數刻意和 frontend/main.js 一致，這樣量到的就是 demo 時的實際表現。
// main.js 改了門檻的話，這裡也要跟著改。
import { PitchDetector } from "../frontend/vendor/pitchy.js";

const WINDOW = 2048;        // main.js: analyser.fftSize
const CLARITY_MIN = 0.85;   // main.js: CLARITY_MIN
const RMS_MIN = 0.01;       // main.js: RMS_MIN
const HZ_MIN = 60, HZ_MAX = 1100;
const HOP_SEC = 0.01;       // 與 scoring/pitch_utils.HOP_SEC 一致

async function readStdin() {
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  const buf = Buffer.concat(chunks);
  // 複製到對齊的 ArrayBuffer，才能安全地當 Float32Array 讀
  return new Float32Array(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
}

const sr = Number(process.argv[2]);
if (!sr) {
  console.error("用法：node experiments/pitchy_f0.mjs <取樣率> < audio.f32");
  process.exit(1);
}

const samples = await readStdin();
const hop = sr * HOP_SEC;
const nFrames = Math.floor(samples.length / hop) + 1;

// 前後各補 WINDOW/2 個 0，讓第 k 個視窗以 k*hop 為中心（和 librosa 的 center=True 相同）
const padded = new Float32Array(samples.length + WINDOW);
padded.set(samples, WINDOW / 2);

const detector = PitchDetector.forFloat32Array(WINDOW);
const f0 = [];

for (let k = 0; k < nFrames; k++) {
  const start = Math.round(k * hop);  // 在 padded 裡，視窗從這裡開始，中心就是原音訊的 k*hop
  const win = padded.subarray(start, start + WINDOW);

  let sum = 0;
  for (const v of win) sum += v * v;
  const rms = Math.sqrt(sum / win.length);

  const [hz, clarity] = detector.findPitch(win, sr);
  const voiced = rms > RMS_MIN && clarity > CLARITY_MIN && hz > HZ_MIN && hz < HZ_MAX;
  f0.push(voiced ? hz : null);
}

process.stdout.write(JSON.stringify({ hop_sec: HOP_SEC, f0 }));
