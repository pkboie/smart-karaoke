// Based on the original v1 RMS beep loopback prototype.
// An acoustic speaker->microphone estimate, NOT a validated one-way input latency.
// Keep the same AudioContext, 880 Hz beep and requestAnimationFrame polling as v1.
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export async function measureLoopbackLatency(onProgress = () => {}, trials = 5) {
  let stream = null;
  let context = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
    });
    context = new AudioContext();
    await context.resume();

    const mic = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    mic.connect(analyser);
    const samples = new Float32Array(analyser.fftSize);
    const rms = () => {
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (const value of samples) sum += value * value;
      return Math.sqrt(sum / samples.length);
    };

    onProgress("測量背景噪音中…");
    let noise = 0;
    for (let i = 0; i < 15; ++i) {
      noise = Math.max(noise, rms());
      await sleep(25);
    }
    const threshold = Math.max(0.005, noise * 3);
    const samplesMs = [];

    for (let trial = 0; trial < trials; ++trial) {
      onProgress(`正在量測 ${trial + 1}/${trials}（請保持安靜）…`);
      const tPlay = context.currentTime + 0.25;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, tPlay);
      gain.gain.exponentialRampToValueAtTime(0.4, tPlay + 0.006);
      gain.gain.exponentialRampToValueAtTime(0.0001, tPlay + 0.09);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(tPlay);
      oscillator.stop(tPlay + 0.1);

      // Same v1 RMS detector (the version known to produce results on this laptop).
      const detected = await new Promise((resolve) => {
        const check = () => {
          const now = context.currentTime;
          if (now >= tPlay && rms() > threshold) return resolve(now);
          if (now > tPlay + 0.6) return resolve(null);
          requestAnimationFrame(check);
        };
        check();
      });
      oscillator.disconnect();
      gain.disconnect();
      if (detected !== null) {
        const latencyMs = (detected - tPlay) * 1000;
        if (latencyMs >= 0 && latencyMs < 600) samplesMs.push(latencyMs);
      }
      await sleep(200);
    }

    if (samplesMs.length === 0) {
      throw new Error("沒有偵測到測試聲，請檢查喇叭、麥克風及瀏覽器音訊輸出。");
    }

    // Post-process only: DO NOT change v1 playback or detection behavior.
    // Very short delays near 0 ms (e.g. 0.7 ms in previous tests) are suspicious.
    // Keep them in samplesMs for transparency, but not in the estimate.
    const candidates = samplesMs.filter((ms) => ms >= 8 && ms < 600);
    // If every sample looks suspicious, still show the raw estimate with
    // reliable=false. Never use it to automatically update the latency field.
    const fallbackToRaw = candidates.length === 0;
    const estimatePool = fallbackToRaw ? samplesMs : candidates;

    const initialMedian = median(estimatePool);
    const deviations = estimatePool.map((v) => Math.abs(v - initialMedian));
    const mad = median(deviations) ?? 0;
    const cutoff = Math.max(25, mad * 3);
    const inliers = estimatePool.filter((v) => Math.abs(v - initialMedian) <= cutoff);
    const used = inliers.length ? inliers : estimatePool;
    const estimate = median(used);
    const range = Math.max(...used) - Math.min(...used);

    // A number can still be shown when confidence is low, but MUST NOT be
    // automatically applied as timing compensation in the UI.
    const reliable = !fallbackToRaw && used.length >= 3 && range <= 30 && samplesMs.length >= 3;
    return {
      samplesMs,                 // all successful RMS detections (including suspicious)
      validSamplesMs: used,      // samples used to compute the rough estimate
      medianMs: estimate,
      rangeMs: range,
      reliable,
      excludedCount: samplesMs.length - used.length,
    };
  } finally {
    stream?.getTracks().forEach((track) => track.stop());
    if (context && context.state !== "closed") await context.close();
  }
}
