// 檢查 frontend/note-judge.js 的 inJudgeWindow() 和 judgeNote()。
//
// 用法：node tests/check_note_judge.mjs
//
// 每個案例的答案都可以手算，算法寫在旁邊的註解。

import { inJudgeWindow, judgeNote, ONSET_SKIP_SEC } from "../frontend/note-judge.js";

let failed = 0;
function check(name, fn) {
  try {
    const msg = fn();
    if (msg) { failed++; console.log(`FAIL  ${name}：${msg}`); }
    else console.log(`ok    ${name}`);
  } catch (e) {
    failed++;
    console.log(`FAIL  ${name}：丟出例外 ${e.message}`);
  }
}
const near = (a, b) => Math.abs(a - b) < 1e-6;
const expectWindow = (t, note, want) => () => {
  const got = inJudgeWindow(t, note);
  return got === want ? "" : `t=${t} 應該是 ${want}，得到 ${got}`;
};
const expectJudge = (midis, target, tol, want) => () => {
  const got = judgeNote(midis, target, tol);
  if (want === null) return got === null ? "" : `應該是 null，得到 ${JSON.stringify(got)}`;
  if (!got) return `應該是 ${JSON.stringify(want)}，得到 ${got}`;
  if (!near(got.centError, want.centError)) return `centError 應該是 ${want.centError}，得到 ${got.centError}`;
  if (got.hit !== want.hit) return `hit 應該是 ${want.hit}，得到 ${got.hit}`;
  return "";
};

console.log(`ONSET_SKIP_SEC = ${ONSET_SKIP_SEC}\n`);

// ---------- inJudgeWindow：長音符 2.0–3.0 秒（開頭跳 80 ms → 2.08 秒才開始算）----------
const long = { start: 2.0, end: 3.0 };
check("長音符：音符之前", expectWindow(1.9, long, false));
check("長音符：開頭 50 ms（滑音）", expectWindow(2.05, long, false));
check("長音符：開頭 100 ms", expectWindow(2.1, long, true));
check("長音符：中間", expectWindow(2.5, long, true));
check("長音符：end 不含（[start, end)）", expectWindow(3.0, long, false));

// ---------- inJudgeWindow：短音符 5.00–5.12 秒（120 ms）----------
// 固定跳 80 ms 只剩 5.08–5.12 = 40 ms ≈ 2 格；規則要求至少留一半 → 5.06 以後一定要算（測 5.07，避開浮點數邊界）
const short = { start: 5.0, end: 5.12 };
check("短音符：後半段 5.07 要算", expectWindow(5.07, short, true));
check("短音符：5.11 要算", expectWindow(5.11, short, true));
check("短音符：end 不含", expectWindow(5.12, short, false));

// ---------- judgeNote ----------
// 沒有格子 → 未判定
check("沒有格子 → null", expectJudge([], 64, 50, null));

// 奇數個：差 [+5, -8, +10] cent → 排序 [-8, +5, +10] → 中位數 +5
check("唱準", expectJudge([64.05, 63.92, 64.10], 64, 50, { centError: 5, hit: true }));

// 中位數 +100，|100| < 100 不成立 → 沒命中；容許 150 就命中
check("偏高 100、容許 100 → 剛好不算", expectJudge([65.0, 65.1, 64.9], 64, 100, { centError: 100, hit: false }));
check("偏高 100、容許 150 → 命中", expectJudge([65.0, 65.1, 64.9], 64, 150, { centError: 100, hit: true }));

// 偏低：差 [-50, -40, -60] → 中位數 -50（符號要保留）
check("偏低 50", expectJudge([63.5, 63.6, 63.4], 64, 100, { centError: -50, hit: true }));

// 一格亂跳（+600）不影響中位數：[0, 0, 0, -600, 0] → 0
check("一格亂跳", expectJudge([64.0, 64.0, 64.0, 70.0, 64.0], 64, 50, { centError: 0, hit: true }));

// 一半格子被偵測成高八度：卡拉 OK 不管八度，這個音符應該算唱準
// 偶數個 → 中位數是中間兩個的平均
check("一半高八度", expectJudge([64.0, 64.1, 76.0, 76.1], 64, 50, { centError: 5, hit: true }));

// ---------- 覆蓋率：唱到的格數 < 0.3 × 應有格數 → 未判定 ----------
// 應有 10 格 → 門檻 3 格：2 格 → null；3 格 → 判定（中位數 +5）
const expectCov = (midis, expectedFrames, want) => () => {
  const got = judgeNote(midis, 64, 50, expectedFrames);
  if (want === null) return got === null ? "" : `應該是 null，得到 ${JSON.stringify(got)}`;
  return got && got.hit === want ? "" : `應該判定 hit=${want}，得到 ${JSON.stringify(got)}`;
};
check("覆蓋率不足：10 格只唱到 2 格 → 未判定", expectCov([64.05, 63.92], 10, null));
check("覆蓋率剛好：10 格唱到 3 格 → 判定", expectCov([64.05, 63.92, 64.10], 10, true));
check("省略 expectedFrames → 不檢查", expectCov([64.05], undefined, true));

console.log(failed ? `\n${failed} 個失敗` : "\n全部通過");
process.exit(failed ? 1 : 0);
