# #6 pkboie：即時判分、音高準確度

> 最後更新：2026-11-19

## 目前在做

- branch：（下一個：`pitch/mir1k-benchmark`）
- 內容：環境與資料集準備完成，接著做修改 A（benchmark 改用 MIR-1K 人工標註）

## 本週目標（對照 PROJECT_PLAN.md）

- [x] 讀 `frontend/main.js` 的 `sample()`、`experiments/pitch_benchmark.py`
- [x] 下載並解壓 MIR-1K、Acapella 到 `data/datasets/`
- [ ] 在 MIR-1K 上跑通 benchmark，產出 10 段的初步數字（11/22）
- [ ] 修改 A：`pitch_benchmark.py --dataset mir1k`（11/27）

## 已完成

- 2026-11-19：資料集解壓完成（MIR-1K 1000 段、Acapella 6 首）；建 `.venv`、產生 demo 歌、`tests/simulate_singing.py` 通過
- 2026-11-19：新增 `docs/git_workflow.md`、`docs/members/`

## 卡住／需要別人

- 給 #3：`data/datasets/acapella_hf/song1/` 少了 `state.json`（其他 5 首都有），`load_from_disk` 可能讀不到，請確認

## 筆記

**MIR-1K 格式**（計畫書 11/17 實測）
- 16 kHz 雙聲道，**右聲道是人聲**：`librosa.load(path, sr=None, mono=False)[1]`
- `PitchLabel/*.pv` 每行一個 MIDI 值，0 = 無聲；**每 20 ms 一筆，第一筆在 20 ms**（鏡像 readme 寫 10 ms 是錯的）
- `scoring/pitch_utils.HOP_SEC` = 10 ms，偵測結果要在 `t = 0.02·(k+1)` 取樣才能和標註對齊

**為什麼要改 benchmark（修改 A）**
- 現在的 `accuracy()` 拿 pYIN 結果比對 `song.json`，但 `song.json` 本身就是 pYIN 產生的 → 自己考自己，數字無效

**E1 要比的方法**：YIN、pYIN、CREPE-tiny、pitchy（McLeod，前端實際使用；需要 Node 腳本）
