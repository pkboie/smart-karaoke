# #6 pkboie：即時判分、音高準確度

> 最後更新：2026-11-23

## 目前在做

- branch：`pitch/mir1k-benchmark`（修改 A，準備開 PR）
- 內容：`experiments/pitch_benchmark.py` 改用 MIR-1K 人工標註當答案，並實作 E1 的五個指標

## 本週目標（對照 PROJECT_PLAN.md）

- [x] 讀 `frontend/main.js` 的 `sample()`、`experiments/pitch_benchmark.py`
- [x] 下載並解壓 MIR-1K、Acapella 到 `data/datasets/`
- [x] 在 MIR-1K 上跑通 benchmark，產出 10 段的初步數字
- [x] 修改 A：`pitch_benchmark.py --dataset mir1k`
- [ ] 開 PR 合併修改 A（11/27 前）
- [ ] MIR-1K 100 段 + 各 SNR 的完整數字

## 已完成

- 2026-11-19：資料集解壓（MIR-1K 1000 段、Acapella 6 首）；建 `.venv`、產生 demo 歌、`tests/simulate_singing.py` 通過
- 2026-11-19：新增 `docs/git_workflow.md`、`docs/members/`
- 2026-11-23：**修改 A 完成**（見下方「給大家的使用說明」）
  - `pitch_benchmark.py` 新增 `--dataset mir1k`：讀 MIR-1K 右聲道（人聲），以 `PitchLabel/*.pv` 人工標註當答案，解決原本「pYIN 自己考自己」的循環論證
  - 實作 E1 指標 `compare_to_reference()`：`rpa`、`rca`、`voicing_recall`、`voicing_fa`、`mean_abs_cents`
  - 結果輸出 CSV（`experiments/results/pitch_benchmark.csv`），每段 × 方法 × SNR 一列
  - 新增 `tests/check_pitch_metrics.py`：用手算的小資料檢查五個指標，全部通過

## E1 初步結果（MIR-1K 隨機 10 段，seed 0，純人聲）

| 方法 | 每秒音訊耗時 | rpa | rca | voicing_recall | voicing_fa | mean_abs_cents |
| --- | --- | --- | --- | --- | --- | --- |
| YIN | 7.8 ms | 0.971 | 0.977 | 1.000 | 0.465 | 11.8 |
| pYIN | 41.2 ms | 0.974 | 0.974 | 0.993 | 0.228 | 11.1 |

- 乾淨人聲上兩者音高都約 97% 正確，差異在有聲判斷與速度（YIN 快約 5 倍）
- **YIN 的 recall = 1.000 不代表它好**：我們 `detect_pitch()` 裡 YIN 的有聲判斷是「音量 > 最大音量 2%」（`scoring/pitch_utils.py:42`），幾乎全判有聲，所以 fa 很高。報告要註明
- YIN 有少量八度錯誤（rca > rpa），pYIN 沒有

## 給大家的使用說明

### 指標定義（報告可直接引用）

| 指標 | 計算方式 | 意義 |
| --- | --- | --- |
| `rpa` Raw Pitch Accuracy | 標註有聲的 frame 中，誤差 < 50 cent 的比例（偵測成無聲算錯，同 MIREX） | 音高正確率 |
| `rca` Raw Chroma Accuracy | 同上，但忽略八度 | `rca − rpa` = 八度錯誤的比例 |
| `voicing_recall` | 標註有聲的 frame 中，偵測也判有聲的比例 | 有唱的地方聽到幾成 |
| `voicing_fa` | 標註無聲的 frame 中，偵測卻判有聲的比例 | 誤報（例如把伴奏當人聲） |
| `mean_abs_cents` | 兩邊都有聲的 frame，折八度後的平均 \|cent 誤差\| | 聽對時有多準 |

### 指令

```bash
python experiments/pitch_benchmark.py --limit 10                       # MIR-1K 隨機 10 段
python experiments/pitch_benchmark.py --limit 100 --methods yin pyin crepe
python experiments/pitch_benchmark.py --snr-db clean 20 10 5 0 -5      # 混入伴奏
python experiments/pitch_benchmark.py --dataset song --song <id>       # 自家歌（song.json 必須手動修正過）
python tests/check_pitch_metrics.py                                    # 檢查指標
```

參數：`--limit 0` = 全部 1000 段；`--seed` 換抽樣；`--out` 改輸出路徑。

### MIR-1K 的格式（自己讀資料時要注意）

- 16 kHz 雙聲道，**右聲道 = 人聲、左聲道 = 伴奏**
- `PitchLabel/*.pv`：每行一個 MIDI 值（可為小數），0 = 無聲
- **每 20 ms 一筆、第一筆在 20 ms**（鏡像 readme 寫 10 ms 是錯的）。已驗證：前後偏移 20 ms 吻合率都會下降

## 卡住／需要別人

- **#1**：E3 可以直接用這支程式，`--snr-db` 會用 MIR-1K 左聲道（伴奏）依指定 SNR 混入人聲，不用另寫混音腳本
- **#2**：CSV 已有 `ms_per_sec` 欄位可當 E2 起點。注意第一段有暖機成本（YIN 38 ms，之後 2–3 ms），請取中位數或丟掉第一次
- **#4**：你的 `codex/difficulty-ui` 改到了 `main.js` 的逐音符判分。我要改 `sample()`（忽略音符開頭 80 ms、改用中位數判定），想等你那支 merge 後再開 `pitch/note-judging`，避免衝突

## 接下來

- 修改 A 開 PR → MIR-1K 100 段 + 各 SNR 的完整數字
- 等 #4 merge 後改進 `sample()` 逐音符判分
- pitchy（前端實際使用的 McLeod）的 Node 腳本，讓 E1 有 4 種方法可比
- CREPE-tiny（確認 torch 是否支援 Python 3.14）
- E1 完整結果與圖（12/04）
