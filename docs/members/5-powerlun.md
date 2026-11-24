# #5：離線處理與特徵工程（Offline Pipeline & Feature Engineering）

> 最後更新：2026-11-23

## 目前在做

- branch：`master`（song6 Demo 已透過 `feature/song6-demo` 合併）
- 內容：
  - 完善正式歌曲的 `song.json` 與歌詞時間對齊。
  - 改善自動音符切分與參考音高品質。
  - 驗證 Acapella 特徵數值及代理參考旋律造成的偏差。
  - 準備第二首正式 Demo 歌曲。

## 本週目標（對照 PROJECT_PLAN.md）

- [x] 完成 DTW 移調估計與初步測試。
- [x] 支援直接從 Arrow 資料集讀取音訊。
- [x] 完成六首歌曲、132 筆特徵提取。
- [x] 確認 Features 與 #3 的 `labels.csv` 可正確合併。
- [x] 將 `features.csv` 整合至 GitHub master。
- [x] 完成第一首正式 Demo 歌曲 song6 的基本處理與前端測試。
- [x] 提交 song6 的 `song.json`、人聲、伴奏及歌詞對齊工具（PR #12）。
- [ ] 完成 song6 的歌詞時間校正與參考音高校正。
- [ ] 完成第二首正式 Demo 歌曲。
- [ ] 驗證特徵品質與代理參考旋律造成的偏差。

## 已完成

### 2026-11-22：Feature Extraction

- 改善 `scoring/features.py` 的 DTW 對齊，加入整體移調估計。
- 修改 `scoring/extract_dataset.py`，支援直接讀取 Hugging Face Arrow 音訊。
- 新增 `offline/build_arrow_references.py`，建立測試用代理參考旋律。
- 成功處理 `song1`～`song6`，每首 22 位歌手，共 132 筆錄音。
- 產生 10 個特徵，涵蓋 `pitch.*`、`rhythm.*`、`contour.*`、`expression.*`。
- 使用 `song`、`singer_id` 合併 Features 與 Labels，132 筆全部配對成功，無缺失值。
- 完成 Git Commits：`473fb36`、`29cd54a`。

### 2026-11-23：Official Song Demo

- 選定 song6《月亮代表我的心》作為第一首正式 Demo。
- 使用 Demucs 分離人聲與伴奏。
- 使用 pYIN 偵測原唱音高，產生參考音符與 `song.json`。
- 使用 Faster-Whisper 嘗試自動辨識中文歌詞與時間戳記。
- 新增 `offline/align_lyrics.py`，根據歌詞時間表將歌詞分配到參考音符。
- 前 35 秒已完成五段歌詞的初步時間對齊。
- 已於 localhost 測試歌曲選單、伴奏播放、音高線及歌詞顯示。
- song6 的 `song.json`、`vocals.wav`、`accompaniment.wav`、`lyrics_timing.json` 及 `align_lyrics.py` 已透過 PR #12 合併至 master（`0fb03a1`）。
- 已使用乾淨 Git Worktree 確認必要檔案存在。

## 卡住／需要別人

- 歌唱人聲的 Whisper 辨識仍有漏字、錯字及時間錯位問題，暫時使用人工標記歌詞區間。
- pYIN 自動切分音符可能受到滑音、顫音與殘留伴奏影響，需要進一步校正。
- 需要進行正式參考旋律與特徵品質驗證。
- 需要與 #3 確認訓練特徵品質及後續 E6 ablation 評估。
- song6 已交付 master，等待其他組員進行跨環境整合測試。

## 筆記

### 1. Feature Extraction

主要流程：

`Arrow audio → pYIN → MIDI pitch → DTW → Feature Extraction → CSV`

相關檔案：

- `scoring/features.py`
- `scoring/extract_dataset.py`
- `offline/build_arrow_references.py`

### 2. 特徵資料格式

輸出位置：`data/features/features.csv`

- 132 筆資料
- 2 個識別欄位：`song`、`singer_id`
- 10 個數值特徵

與 #3 的 `labels.csv` 使用以下欄位合併：

```python
merged = features.merge(
    labels,
    on=["song", "singer_id"],
    validate="one_to_one"
)
```

Expression 訓練目標：

`expression = (vibrato + dynamic) / 2`

### 3. 正式歌曲處理

處理流程：

`Original Audio → Demucs → Vocals / Accompaniment → pYIN → song.json`

歌詞處理流程：

`Lyrics + Timing → align_lyrics.py → song.json`

正式 Demo 資料位置：

`data/songs/song6/`

主要檔案：

- `song.json`：歌曲資訊、參考音符與歌詞
- `vocals.wav`：分離後的人聲
- `accompaniment.wav`：分離後的伴奏
- `lyrics_timing.json`：歌詞時間設定

執行歌詞對齊：

```bash
python offline/align_lyrics.py
```

目前歌曲約 205 秒，前 35 秒已加入初步對齊歌詞，剩餘段落尚未完成。

### 4. 已知限制

- 目前使用代理參考旋律產生的 132 筆 Features，適合測試 ML 訓練流程，但尚未完成特徵品質驗證。
- `singer_id=0` 作為代理參考可能造成特徵偏差。
- song6 的正式參考音高由 pYIN 自動產生，尚未完成全面人工校正。
- `align_lyrics.py` 目前依照提供的時間範圍分配歌詞，並非真正的音訊強制對齊，因此歌詞可能提前、延後或顯示過快。
- 後續目標是建立可重複使用的歌詞自動對齊流程，減少人工標記秒數的工作。