// 逐音符判分（負責人：#6）
// 純函式、不碰 DOM：main.js 在瀏覽器裡 import，tests/check_note_judge.mjs 在 Node 裡測。
// 判定方式和後端 scoring/features.py 的 per_note 一致：一個音符取一個中位數再判斷命中。

export const ONSET_SKIP_SEC = 0.08;   // 音符開頭的滑音不算（約 4 格 @ hop 1024 / 48 kHz）
export const MIN_COVERAGE = 0.3;      // 唱到的格數 ÷ 音符應有格數，低於這個 → 未判定（和後端 coverage < 0.3 一致）

// 兩個 MIDI 的差 → cent，折到 [-600, 600)，忽略八度（和 main.js 原本的 foldCents 相同）
export const foldCents = (d) => ((((d * 100) % 1200) + 1800) % 1200) - 600;

/**
 * 時間 t 的這一格要不要拿來判斷 note？
 *
 * @param {number} t     這一格的時間（秒，已扣掉延遲）
 * @param {{start: number, end: number}} note  目標音符（秒），區間是 [start, end)
 * @returns {boolean}
 *
 * 規則：
 *   - 不在 [start, end) 裡 → false
 *   - 音符開頭 ONSET_SKIP_SEC 內 → false（滑音）
 *   - 但短音符不能整個被跳掉：至少要留一半長度可以判斷
 */
export function inJudgeWindow(t, note) {
  if (t < note.start || t >= note.end) return false;
  const skip = Math.min(ONSET_SKIP_SEC, (note.end - note.start) / 2);
  return t - note.start >= skip;
}

/**
 * 一個音符唱完後，判斷有沒有命中。
 *
 * @param {number[]} midis       這個音符判斷窗內所有有聲格的 MIDI（小數）
 * @param {number}   targetMidi  目標音高
 * @param {number}   tolerance   容許誤差（cent），|誤差| < tolerance 才算命中
 * @param {number}   expectedFrames  整個音符應有的格數（音符長度 ÷ hop）；省略 = 不檢查覆蓋率
 * @returns {{centError: number, hit: boolean} | null}  沒有格子或唱到的太少時回傳 null（未判定）
 *
 * centError 是這個音符的代表誤差（cent，正 = 偏高），要忽略八度。
 */
export function judgeNote(midis, targetMidi, tolerance, expectedFrames = 0) {
  if (midis.length === 0 || midis.length < MIN_COVERAGE * expectedFrames) return null;
  // 先每格折八度再取中位數：若先取中位數，一半高八度的格子會把中位數拉到兩群中間
  const cents = midis.map((m) => foldCents(m - targetMidi)).sort((a, b) => a - b);
  const mid = Math.floor(cents.length / 2);
  const centError = cents.length % 2 === 1 ? cents[mid] : (cents[mid - 1] + cents[mid]) / 2;
  return { centError, hit: Math.abs(centError) < tolerance };
}
