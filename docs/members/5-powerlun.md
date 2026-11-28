
# #5：離線處理與特徵工程（Offline Pipeline & Feature Engineering）

> 最後更新：2026-11-28  
> 負責人：powerlun

## 目前在做

- Branch：`experiment/reference-singer-comparison`（Key Shift 修復待提交／PR 合併；以 GitHub 最新狀態為準）
- 目前重點：
  - 已產生 `features_v3_experimental.csv`（132 筆，最高分 Singer 參考，含八度與 Key Shift 處理），#3 已完成探索性訓練比較。
  - 修復共用 `extract_features()` 對固定伴奏 Demo 的 Key Shift 副作用，待提交／合併修正。
  - 待建立**不利用測試歌曲標籤**的正式參考來源，才能提供無標籤洩漏的 E4 評估。
  - 兩首正式 Demo 的音檔與 JSON 已合併至 `master`，但 E1 人工 Pitch Ground Truth 尚待完成。

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
- [x] 與 #3 完成 v1／v2 及探索性 v3 的初步模型比較（v3 不可用於無洩漏 E4 成績）。
- [x] 六首歌 Singer 0 與高分 Singer 參考對照診斷。
- [x] 產生 `features_v3_experimental.csv`（132 筆，實驗用途）。
- [x] 模擬測試確認固定伴奏 Demo 關閉 Key Shift 後，偏高半音恢復扣分。
- [ ] 將 Demo／離線 Key Shift 分流修正合併至 `master`。
- [ ] 建立標籤獨立的正式 Features 參考方案並重跑無洩漏評估。
- [ ] 完成正式 song6 的完整歌詞與參考音高校正。
- [x] 完成第二首正式 Demo song2 的初步版本，音檔及 JSON 已合併至 `master`（仍待音高校正）。

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

### 2026-11-28：Reference Singer 診斷、Features v3 與 Demo Key Shift 修復

#### 1. Singer 0 參考偏差診斷

- 使用 `offline/compare_reference_singers.py` 比較六首歌的 Singer 0 與各首**最高分 Singer**；每首比較時排除兩名參考者，因此每首對照 20 位歌手。
- 新參考：song1=7、song2=7、song3=15、song4=20、song5=7、song6=15。
- 六首 Spearman ρ 的**逐首算術平均**如下（不是合併樣本的 ρ）：

| 特徵 | Singer 0 | 高分 Singer | 預期方向 |
|---|---:|---:|---|
| `pitch.median_abs_cents` | -0.094 | -0.010 | 負 |
| `pitch.hit_rate_100c` | +0.020 | +0.022 | 正 |
| `contour.interval_accuracy` | -0.237 | +0.394 | 正 |
| `contour.note_coverage` | -0.303 | +0.461 | 正 |
| `rhythm.median_abs_onset_ms` | +0.160 | -0.357 | 負 |

- Contour／Rhythm 的相關方向在六首歌都變得合理，但 Pitch 未明顯改善；此對照屬**探索性診斷**，不是正式模型評估。

#### 2. Features v3（已產生並供 #3 實驗）

- 產出：`data/features/features_v3_experimental.csv`，共六首 × 22 位 = **132 筆不重複 `(song, singer_id)`**。
- 產生器：`offline/build_features_v3_experimental.py`；參考選擇紀錄：`data/features/reference_experiments/v3_reference_selection.csv`；限制說明：`data/features/reference_experiments/v3_README.txt`。
- 使用最高分 Singer 當代理參考，修正逐影格八度折算與每音符的整體移調處理。
- **關鍵限制（請 #3 注意）：** 最高分 Singer 是藉由本首歌 `labels.csv` 選出的，正式 LOSO 的測試歌曲標籤因而參與特徵建構，存在 **Label Leakage**。即使排除六筆參考歌手自身資料，仍不能宣稱無洩漏。**v3 只能作為診斷性／探索性 E4 實驗，不得作為最終無洩漏 LOSO 成績。**
- #3 回報 v3 模型在模擬情境有正常唱 93 ＞ 拖拍 75 ＞ 亂唱 60 的改善；但這不代表模型已通過正式評估，且 `expression.vibrato_cents` 與人工評分仍呈負相關（約 -0.216），待改善顫音特徵定義。

#### 3. 修復 PR #28 對 Demo 的 Key Shift 副作用

- 問題：原本為 Acapella 特徵加入 `usr_aligned` 的補償後，共用 `extract_features()` 讓**固定伴奏** Demo 的「整首偏高半音」也被補償掉，模擬分數一度變成 95（與正常唱相同），而前端即時判斷並未使用相同補償。
- 修法：`scoring/features.py` 新增 `apply_key_shift=False`（預設關閉）；離線路徑 `scoring/extract_dataset.py` 和 `offline/build_features_v3_experimental.py` 明確使用 `apply_key_shift=True`。Demo 的 `backend/app.py` 維持預設 `False`。
- **本機已實測** `python tests/simulate_singing.py`：

| 情境 | 總分 | 音準分 |
|---|---:|---:|
| 正常唱 | 95 | 100 |
| 偏高半音 | 51 | 0 |
| 拖拍 350ms | 71 | 100 |
| 亂唱 | 18 | 4 |

- 因此 Demo 規則式評分的半音偏移懲罰在**本機模擬測試**已恢復；仍需 PR 合併及跨機驗收。**未因這次分流修復重生 v3 CSV**：v3 原先就有啟用 Key Shift，當前修改是把兩種呼叫場景明確分離。

#### 4. 正式 Demo 交付現況

- `data/songs/song6/`：《月亮代表我的心》，前 60 秒歌詞／音高已有展示候選。
- `data/songs/song2/`：《我只在乎你》，約 105 秒歌詞／音高候選；`song.json`、`lyrics_timing.json`、`vocals.wav`、`accompaniment.wav` 已合併到 `master`。
- 兩首仍以自動 pYIN 產生的參考音高為主，**尚不是 E1 要求的獨立人工音高校正 Ground Truth**。

## 卡住／需要別人

- **#3：** 現有 v3 僅可用於探索性模型分析；正式 E4 需要獨立於測試歌曲 Labels 的參考旋律及重新評估，不能把 v3 的 LOSO 當最終成績。
- **#4／整合：** 待 Key Shift 分流修正合併 `master` 後，在其他設備確認固定伴奏 Demo 的半音偏移仍會扣分；正式展示暫沿用經測試的規則式評分。
- **#5：** 評估原唱人聲參考的歌曲版本相容性，或設計其他不依賴測試標籤的參考選擇流程，再產生後續正式 Features。
- **E1：** song2、song6 需完成各 30～60 秒的獨立人工音高標註；自動 pYIN 候選不能直接作 Ground Truth。
- **特徵改進：** `expression.vibrato_cents` 仍可能將不穩定音高抖動當成顫音；後續考慮 4–8 Hz 頻帶能量與穩定有聲區間限制。

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

目前正式 song6 約 205 秒，前 60 秒已加入初步對齊歌詞；完整人工音高校正仍未完成。

### 4. Acapella 與正式 Demo 的區別

- `data/songs/song6/song.json`：正式 Karaoke Demo。
- `data/songs/acapella_song6/song.json`：ML 資料集專用代理參考。

兩者來源及用途不同，不能混用。

### 5. 已知限制與後續方向

- 代理參考旋律可能造成 Singer 0 的自我參考偏差。
- 不同歌手可能演唱不同長度的片段，部分時間對齊結果仍可能不可靠。
- 目前移調估計偏保守，尚未確認能穩定辨識真正的升降 Key。
- 實驗性 v3 使用評分標籤挑選高分參考歌手，已明確標示 Label Leakage，**不得作為正式無洩漏 E4 結果**。
- #3 已完成探索性 v3 比較；接下來應以無標籤洩漏的參考來源重做正式 E4 評估。
- 持續改善正式 Demo 的參考音高、歌詞時間對齊與 E1 人工標註。
