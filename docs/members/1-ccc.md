# #1：收音、VAD、Noise Robustness

> 最後更新：2026-11-23

## 目前在做

- branch：`mic/mir1k-loader`、`mic/audio-capture`、`mic/noise-robustness`
- 內容：W1、W2 主要功能已完成初步實作與測試，準備整理 PR。接下來會進行 E3 Noise Robustness 實驗。

## 本週目標（對照 PROJECT_PLAN.md）

- [x] 下載 MIR-1K，確認人聲及伴奏聲道
- [x] 完成 MIR-1K 音訊與 PitchLabel 讀取
- [x] 熟悉 `startMic()`、`RMS_MIN` 與現有 VAD
- [x] 改善 VAD，依據環境噪音自動調整 RMS threshold
- [x] 使用 AudioWorklet 改善收音流程
- [x] 完成 E3 SNR 混音腳本
- [ ] 整理並提交 PR

## 已完成

- 2026-11-23：
  - 完成 `mir1k_loader.py`，可以讀取 MIR-1K 的人聲、伴奏與人工音高標註。
  - 確認 MIR-1K 左聲道為伴奏、右聲道為人聲。
  - 改善 VAD：開始演唱前測量 1 秒環境噪音，自動設定 RMS threshold。
  - 測試安靜環境及電風扇噪音，確認 threshold 會隨環境變化。
  - 新增 AudioWorklet，將音訊收集與畫面更新分開。
  - 實際測試網頁收音、即時音高線與後端評分，確認正常。
  - 完成 E3 SNR 混音，可產生 Clean、20、10、5、0、−5 dB 六種條件的音訊。

## 卡住／需要別人

- #6：W3 的 E3 實驗需要共用 MIR-1K benchmark，才能比較不同 SNR 下的音高準確率。
- #2：目前 AudioWorklet 仍使用 `audio.currentTime` 記錄音高時間，需要進一步確認音訊與伴奏的時間同步。

## 筆記

### 1. MIR-1K

- 資料集路徑：`data/datasets/mir1k/MIR-1K/`
- 左聲道：伴奏；右聲道：人聲
- 取樣率：16 kHz
- `PitchLabel/*.pv`：人工 MIDI 音高標註，0 代表無聲，每 20 ms 一筆
- 讀取工具：`experiments/mir1k_loader.py`

### 2. Adaptive VAD

原本固定使用 `RMS_MIN = 0.01`。現在會在演唱前測量 1 秒環境噪音，根據背景 RMS 自動調整門檻。

電風扇測試確認門檻會提高，但尚未正式測量 VAD 的準確率。

### 3. AudioWorklet

- 新增 `frontend/mic-processor.js`
- 修改 `frontend/main.js`
- 以 AudioWorklet 收集音訊，pitchy 仍負責音高偵測
- 保留原本的 trace JSON 格式與即時判分功能

### 4. E3 SNR Mixing

執行方式：

```bash
python experiments/noise_robustness.py
```

產生 Clean、20、10、5、0、−5 dB 六種音訊，輸出到 `data/experiments/noise_robustness/`。

目前已完成混音與基本 SNR 驗證，W3 再進行完整音高準確率比較。