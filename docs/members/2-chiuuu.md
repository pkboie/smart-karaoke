# #2：延遲校正與效能量測

> 最後更新：2026-11-28

## 目前在做

- 工作範圍：修改 H（延遲校正）、修改 G（收音與伴奏時間基準）、修改 C（Benchmark 效能量測）。
- 相關分支：
  - `benchmark/memory`：修改 C；已 commit（`4d3f772`）並 push，PR 合併狀態待確認。
  - `latency/hg-integration`：修改 H/G；已透過 PR 合併至 `master`（merge commit `b7f15f7`）。
- 目前重點：保留可運作的延遲校正介面，整理不穩定的量測結果；請組員協助跨裝置測試，並準備 W3 的 E2 實驗。

## W2 目標與進度（11/23–11/29，對照 PROJECT_PLAN.md）

- [x] **修改 C：Benchmark 加入記憶體量測。** 已輸出 `ms_per_sec`、`peak_rss_mb`、`python_alloc_peak_mb`，以 Demo 歌曲測試 YIN、pYIN、pitchy，皆可執行；程式已 push。
- [x] **修改 H：前端延遲校正流程整合。** 已新增校正按鈕、Beep 測試、五次量測、結果顯示與穩定性判斷；若結果不可靠則保留手動輸入值。
- [x] **修改 G：AudioContext／AudioWorklet 時間處理整合與基本功能測試。** 小星星 Demo 已確認伴奏、即時音高線、評分結果及 trace 儲存正常。
- [ ] **校正精度與時間同步驗證。** 延遲量測結果波動仍大；目前的功能測試尚不能證明歌聲與伴奏的時間精確對齊。
- [ ] **三台組員筆電與耳機量測。** 尚待其他組員實測並整理量測表；耳機情境需另外明確定義量測方式。
- [ ] 確認 `benchmark/memory` PR 的 Review／Merge 狀態。

## 已完成

- **2026-11-23（W1 收尾）**
  - 跑通 Quick Start，包括產生 Demo 歌及 `tests/simulate_singing.py`。
  - 完成獨立的 `frontend/latency_prototype.html`：播放 Beep、透過麥克風偵測並顯示毫秒數。
  - 三次初測結果為 **61.3、170.7、32.0 ms**；觀察到明顯波動。
- **2026-11-28（W2）**
  - 在 `experiments/pitch_benchmark.py` 加入記憶體監測，並更新 `requirements.txt`（`psutil`）。測試可產生含記憶體欄位的 CSV。
  - 初步 Demo 測試（啟用 memory profiler，**非正式 E2 結論**）：

    | 方法 | ms_per_sec | peak_rss_mb | python_alloc_peak_mb |
    | --- | ---: | ---: | ---: |
    | YIN | 782.32 | 194.21 | 65.27 |
    | pYIN | 1860.99 | 350.51 | 138.29 |
    | pitchy | 45.40 | 152.97 | 8.81 |

  - 將 H/G 的前端修改整合至 `frontend/index.html`、`frontend/main.js`、`frontend/mic-processor.js`，新增 `frontend/latency-calibration.js`，並合併至 `master`。
  - 已以小星星 Demo 測試：伴奏正常播放、白色音高線正常、結束後可評分並產生 trace。

## 卡住／需要別人

- **延遲校正不穩定：** 聲學回錄多次出現近乎 0 ms 或相差很大的數據。現採用可顯示原始量測值、過濾部分可疑值且不穩定時**不自動套用**的保守作法；仍可手動設定補償。
- **需要其他兩位組員協助測試：** 使用筆電喇叭＋內建麥克風，各執行數組延遲測試，提供設備、原始五次數值、顯示的估計值及穩定性提示。失敗結果也保留。
- **需要確認耳機測試方法：** 喇叭到麥克風的聲學回錄不能直接當成耳機的輸入延遲；先分開紀錄耳機演唱功能測試與可驗證的延遲測量。
- **與 #1／#4／#6 協調：** 持續驗證時間同步，並留意後續 `main.js`／`processAudioFrame()` 的修改，避免功能衝突。

## W3 下一步（11/30–12/06）

- [ ] **12/04 前完成 E2 Efficiency：** 在一致的測試環境與同一批片段上比較各方法處理時間和記憶體；每個方法獨立執行三次，考慮暖機、取中位數，產出 CSV 與圖。
- [ ] **瀏覽器端量測 pitchy：** 記錄每個 frame 的實際處理耗時與端到端延遲；不要把 Node.js 啟動成本當作 pitchy 演算法的速度。
- [ ] 撰寫英文投影片 Motivation／Method 前半，彙整各組員後續提供的實驗成果。

## 筆記與限制

- `latency-calibration.js` 現在主要使用麥克風 RMS 偵測 Beep；**量到的是粗略的喇叭到麥克風聲學回錄延遲**，包含音訊裝置、聲音傳播及偵測誤差，並非已驗證的單向演唱補償值。
- 小星星端到端功能通過，只代表播放、收音、評分流程可執行；**尚未量化收音和伴奏的同步誤差**。
- E2 的初步記憶體量測包含 Python 主程序／子程序 RSS，並有 profiler 開銷；pitchy 另有 Node.js 啟動與取樣差異，正式報告需清楚界定比較範圍。
- `data/` 下的錄音、trace 等測試資料不會跟著 Git 提交；提交前避免直接使用 `git add .`。
