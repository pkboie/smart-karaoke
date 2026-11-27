
# #5：離線處理與特徵工程（Offline Pipeline & Feature Engineering）

> 最後更新：2026-11-28  
> 負責人：powerlun

## 目前在做

- Branch：請以本次提交前的 `git branch --show-current` 為準（歷史 W2 開發分支：`feature/w2-offline-features-v2`）
- 目前重點：
  - 完成 W2 新版 Features 的 GitHub 提交及與 #3 的交接。
  - 協助 #3 比較新版與舊版 Features 的模型表現。
  - 持續改善正式 Demo 的參考音高與歌詞時間對齊。
  - song6 已有前 60 秒含歌詞 v1；song2 已在 localhost 測試約 105 秒的音符／歌詞候選版本。
  - 準備兩首 Demo 的 JSON 交付、音檔雲端分享與跨環境驗收。

## 本週目標（對照 PROJECT_PLAN.md）

- [x] 完成 DTW 對齊與移調估計的初步實作。
- [x] 支援直接從 Arrow 資料集讀取音訊。
- [x] 完成六首歌曲、132 筆特徵提取。
- [x] 確認 Features 與 Labels 可以使用 `(song, singer_id)` 合併。
- [x] 完成第一版 `features.csv` 並整合至 master。
- [x] 完成第一首正式 Demo song6 的基本處理與前端測試。
- [x] 透過 PR #12 提交正式 song6 Demo 資料及歌詞對齊工具。
- [x] 改善全域時間對齊、移調估計與音符切分。
- [x] 產生新版 `features_v2.csv`，共 132 筆資料。
- [x] 完成新版 Features 的基本資料品質檢查。
- [x] 將 Acapella song6 參考旋律與正式 Karaoke Demo 分離。
- [ ] 完成新版 Features 的模型效果驗證（與 #3 合作）。
- [x] 將 song6 的歌詞與音符候選版本延伸至前 60 秒，並完成 localhost 顯示測試。
- [x] 建立第二首 Demo song2《我只在乎你》的音訊分離、MIDI 與歌詞候選版本，並在 localhost 測試約 105 秒。
- [ ] 完成兩首 Demo 的人工音高、逐字節拍校正及跨環境驗收。
- [ ] 完成兩首 Demo 資料的正式分享與交付。

## 已完成

### 2026-11-22：Feature Extraction

- 改善 `scoring/features.py` 的 DTW 對齊，加入整體移調估計。
- 修改 `scoring/extract_dataset.py`，支援直接讀取 Hugging Face Arrow 音訊。
- 新增 `offline/build_arrow_references.py`，建立測試用代理參考旋律。
- 成功處理 `song1`～`song6`，每首 22 位歌手，共 132 筆錄音。
- 產生 10 個數值特徵，涵蓋：
  - Pitch：音高誤差與音高命中率。
  - Rhythm：起音時間誤差、提前與延後比例。
  - Contour：旋律音程準確率、音符覆蓋率。
  - Expression：顫音幅度、音量變化。
- 使用 `(song, singer_id)` 合併 Features 與 Labels。
- 132 筆資料全部配對成功，無缺失值。
- 完成 Git Commits：`473fb36`、`29cd54a`。

### 2026-11-23：Official Song Demo

- 選定 song6《月亮代表我的心》作為第一首正式 Demo。
- 使用 Demucs 分離人聲與伴奏。
- 使用 pYIN 偵測原唱音高，產生參考音符與 `song.json`。
- 使用 Faster-Whisper 嘗試自動辨識中文歌詞與時間戳記。
- 新增 `offline/align_lyrics.py`，根據歌詞時間表分配歌詞至參考音符。
- 前 35 秒已完成五段歌詞的初步時間對齊。
- 已於 localhost 測試歌曲選單、伴奏播放、音高線及歌詞顯示。
- 正式 song6 的相關資料已透過 PR #12 合併至 master（`0fb03a1`）。
- 已使用乾淨 Git Worktree 確認必要檔案存在。

### 2026-11-27：W2 Feature Engineering Improvements

#### 1. 問題分析

針對第一版 Features 進行品質檢查，發現：

- 使用 Singer 0 作為代理參考旋律，會產生自我參考偏差。
- 同一首歌曲的不同歌手，錄音長度與起唱時間可能差異很大。
- 原本的全域時間對齊搜尋範圍不足。
- 初版移調估計容易出現搜尋邊界值，例如 `key_shift = -6`。
- 自動音高切分可能受到靜音、短暫音高跳動與 pYIN 誤判影響。

#### 2. 演算法改善

修改 `scoring/features.py`：

- 改善全域時間偏移估計，支援較大幅度的起唱時間差異。
- 結合 voiced activity 與音高相似度尋找候選對齊位置。
- 使用 DTW 比較參考旋律與演唱音高。
- 調整移調估計方式，降低不同移調候選使用不同配對路徑造成的干擾。
- 保留原本的 10 個 ML 特徵。
- 額外輸出 `offset_sec` 與 `key_shift` 作為診斷資訊。

修改 `scoring/pitch_utils.py`：

- 改善 `segment_notes()` 的音高平滑。
- 避免將無聲影格的 `NaN` 當成 MIDI 0 參與平滑。
- 保留既有音高偵測與音符切分介面。

#### 3. Acapella song6 參考旋律

因為 `data/songs/song6/song.json` 已用於正式 Karaoke Demo，因此另外建立：

`data/songs/acapella_song6/song.json`

- 使用 Acapella song6 的 Singer 0 音訊建立代理參考。
- 音訊長度約 76.743 秒。
- 偵測並切分出 154 個參考音符。
- 不覆蓋正式 Demo 的歌曲資訊、歌詞與伴奏。

#### 4. 新版 Features

產生：

`data/features/features_v2.csv`

資料規格：

- 六首歌曲：`song1`～`song6`。
- 每首 22 位歌手，共 132 筆。
- 使用 `(song, singer_id)` 作為合併主鍵。
- 保留原本的 10 個數值特徵。
- 增加 `offset_sec` 與 `key_shift` 診斷欄位。
- 無重複主鍵、NaN 或 Inf。
- 保留原本的 `features.csv` 作為 baseline。

#### 5. 新舊 Features 比較

六首歌曲共 132 筆資料的平均結果：

| 指標 | 舊版 | 新版 |
|---|---:|---:|
| Pitch Median Absolute Error | 234.4 cents | 219.5 cents |
| Pitch Hit Rate (±100 cents) | 31.4% | 37.6% |
| Rhythm Median Absolute Onset Error | 709.1 ms | 393.6 ms |
| Note Coverage | 93.0% | 94.1% |

整體而言，新版在多項特徵統計上有所改善，尤其是節奏起音誤差。

但這些是演算法輸出的數值變化，**尚不能證明真實評分準確率提高**，仍需 #3 使用一致的模型訓練及評估方式進行比較。

新版的移調估計偏保守，132 筆資料中有 127 筆 `key_shift = 0`，因此目前不將該欄位視為已驗證的可靠移調標籤。

### 2026-11-28：Two Demo Songs — Lyrics & Localhost Integration

#### song6《月亮代表我的心》

- 將原先前 35 秒的歌詞初稿延伸至前 60 秒，更新 `data/songs/song6/song.json` 與 `lyrics_timing.json`。
- 依人工聽辨提供的句子時間修正 36～60 秒歌詞段落；最後一句確認於 55～60 秒。
- 結構測試：完整 `song.json` 共 363 個音符；前 60 秒 117 個音符；9 段歌詞時間資訊；音符與歌詞基本格式檢查通過。
- localhost 已確認可顯示前 60 秒歌詞與音高線。
- **限制**：歌詞字級／節拍對齊仍有偏差；pYIN 偵測的 MIDI 尚未取得完整人工 Ground Truth，不能聲稱音高準確度已驗收。

#### song2《我只在乎你》

- 新增第二首正式 Demo，使用 Demucs 由 `source.mp3` 分離 `vocals.wav`、`accompaniment.wav`。
- 以 pYIN 先建立前 60 秒 MIDI 初稿（91 個音符），再運用專案現有的 `scoring.pitch_utils` 將後段延伸至約 106 秒。
- 依人工聽辨記錄 33～105 秒共 17 段歌詞時間，儲存於 `data/songs/song2/lyrics_timing.json`，並產生 `song.json` 的逐音符歌詞候選標記。
- 已於 localhost 檢視延伸後的音符、歌詞與播放效果；目前可視為**可展示的候選 v1**。
- 特別保留舊有 Acapella song2 參考檔備份，避免與正式 Demo 的 `song.json` 混用。
- **限制**：音高、音符切割與逐字對齊仍是自動結果／粗略人工句級時間，尚未完成標準答案驗證。

#### Git 交付規劃

- 本次優先提交 song2、song6 的 `song.json`、`lyrics_timing.json` 以及此進度文件。
- 原曲 MP3、大型 WAV 與本地備份暫不新增至 Git；依團隊規劃以雲端硬碟分享音訊。
- 用 `git status --short`、`git diff --cached --stat` 審核實際提交內容，避免把診斷腳本、暫存資料或其他分支修正混入。
- 兩首 Demo 的 JSON 需在其他組員環境驗證與音訊匹配後，才能視為正式交付完成。

## 卡住／需要別人

- 需要 #3 協助比較 `features.csv` 與 `features_v2.csv` 在相同模型設定下的訓練與測試結果。
- 目前仍使用 Singer 0 作為代理參考旋律，可能造成自我參考偏差。
- 時間對齊與移調估計尚未使用人工標註的標準答案進行驗證。
- 歌唱人聲的 Whisper 辨識仍有漏字、錯字與時間錯位問題。
- song6、song2 的 pYIN 音符及歌詞時間仍需進一步人工校正；目前兩首均僅是候選 v1。
- 正式 Demo 仍需要其他組員協助進行跨環境整合測試，並確認兩首音檔的雲端分享方式。

## 筆記

### 1. Feature Extraction Pipeline

主要流程：

`Arrow Audio → pYIN → MIDI Pitch → Global Time Alignment → DTW → Feature Extraction → CSV`

相關檔案：

- `scoring/features.py`
- `scoring/pitch_utils.py`
- `scoring/extract_dataset.py`
- `offline/build_arrow_references.py`

### 2. 特徵資料格式

第一版：

`data/features/features.csv`

第二版：

`data/features/features_v2.csv`

第二版包含：

- 132 筆資料。
- 2 個識別欄位：`song`、`singer_id`。
- 10 個 ML 數值特徵。
- 2 個診斷欄位：`offset_sec`、`key_shift`。

與 #3 的 `labels.csv` 合併：

```python
merged = features.merge(
    labels,
    on=["song", "singer_id"],
    validate="one_to_one"
)
```

訓練時建議先沿用原本 10 個特徵，暫時不要直接把 `offset_sec`、`key_shift` 加入訓練，以便公平比較新舊版本。

Expression 訓練目標：

`expression = (vibrato + dynamic) / 2`

### 3. 正式歌曲處理

正式 Demo：

`data/songs/song6/`

處理流程：

`Original Audio → Demucs → Vocals / Accompaniment → pYIN → song.json`

歌詞處理：

`Lyrics + Timing → align_lyrics.py → song.json`

執行：

```bash
python offline/align_lyrics.py
```

目前正式 song6 全曲約 205 秒，前 60 秒已有歌詞初步對齊；song2 全曲約 261 秒，約前 105 秒已有音高與歌詞候選資料。兩首皆尚未完成音高與逐字節拍人工驗證。

### 4. Acapella 與正式 Demo 的區別

- `data/songs/song6/song.json`：正式 Karaoke Demo。
- `data/songs/acapella_song6/song.json`：ML 資料集專用代理參考。

兩者來源及用途不同，不能混用。

### 5. 已知限制與後續方向

- 代理參考旋律可能造成 Singer 0 的自我參考偏差。
- 不同歌手可能演唱不同長度的片段，部分時間對齊結果仍可能不可靠。
- 目前移調估計偏保守，尚未確認能穩定辨識真正的升降 Key。
- 使用評分標籤挑選高分參考歌手可能造成標籤洩漏，因此尚未採用於正式 Features。
- 下一步由 #3 進行新舊 Features 模型比較，並視結果決定是否採用新版。
- 持續改善兩首正式 Demo 的參考音高、歌詞時間對齊，完成雲端檔案分享與跨環境測試。
