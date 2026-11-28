# #3 ed：評分模型與建議

> 最後更新：2026-11-28

## 目前在做

- branch：`model/acapella-e4`（已同步至 `0dacf3a`）
- 內容：已完成 #5 新版 `data/features/features_v2.csv`（132 筆、沿用原本 10 個特徵，不含 `offset_sec` 與 `key_shift`）與舊版 `features.csv` 的公平對照實驗，並確認 `tests/simulate_singing.py` 在新版模型下的行為與特徵偏差原因。

## 本週目標（對照 PROJECT_PLAN.md）

- [x] 下載 Acapella 資料集，整理 132 筆 × 9 面向分數成 `data/datasets/acapella/labels.csv`
- [x] 聽出 `song1`–`song6` 的真實歌名並回報群組（供 #5 找原曲與全組選 Demo 歌）
- [x] 繪製分數分布圖並整理資料檢視筆記
- [x] 跑通 `python scoring/train.py --demo` 熟悉現有訓練管線
- [x] 改寫 `scoring/train.py`（支援 `--target`、`--drop-group`、雙指標 Spearman $\rho$、Bootstrap 95% CI 與自動輸出結果圖表）
- [x] 改寫 `scoring/scorer.py`（支援自動偵測並載入 `overall`、`pitch`、`rhythm`、`expression` 模型，無模型時自動退回規則式）
- [x] 合併 132 筆 features 與 labels，跑初步四目標 LOSO
- [x] 修正訓練欄位篩選，排除評分標籤造成的特徵洩漏
- [x] 以修正後流程重跑 Overall 四組 feature ablation
- [x] 無模型的規則式降級通過 `tests/simulate_singing.py`
- [x] 合併 `features_v2.csv` 與 `labels.csv`（`data/features/all_v2.csv`），在相同模型設定下完成新舊 Features 四目標與 Ablation 比較
- [x] 確認新版模型與規則式在 `tests/simulate_singing.py` 的分數行為（確認模型受 Singer 0 偏差影響尚不適合作為 Demo 評分器，Demo 維持規則式 fallback）
- [ ] 待 #5 改用「非低分代理參考」（或正式 Demo 原曲／高分參考備案）後重跑 E4 並定稿，與全組自錄後微調 `make_tips()`

## 已完成

- 2026-11-21：跑通 `scoring/train.py --demo` 確認原始訓練流程（Ridge LOSO 驗證 Spearman $\rho = 0.923$、$\text{MAE} = 0.374$）。
- 2026-11-21：合併 Hugging Face Acapella 6 個 split（共 132 筆）輸出 `data/datasets/acapella/labels.csv`，並匯出試聽檔辨識出 6 首歌名。
- 2026-11-21：產出四大目標（`overall_performance`、`pitch`、`rhythm`、`expression`）的統計摘要與分布圖（`score_distributions.png`、`score_by_song_boxplot.png`）。
- 2026-11-21：完成 `scoring/train.py` 升級（W2 修改 D）並以 `--demo` 模式測通多目標訓練、特徵消融與 `experiments/results/` 圖表輸出。
- 2026-11-21：完成 `scoring/scorer.py` 升級（W3 修改 E），後端現已支援依 `models/<target>.joblib` 切換各面向模型給分。
- 2026-11-24：將 `data/features/features.csv` 與 `labels.csv` 以 `song`、`singer_id` 一對一合併，共 132 筆；修正 `train.py` 僅選取 `pitch.*`、`rhythm.*`、`contour.*`、`expression.*` 欄位，排除標籤洩漏。v1 Overall Ridge LOSO Spearman $\rho=0.372$、MAE $=1.686$。
- 2026-11-28：
  - 為 `scoring/train.py` 新增 `--prefix` 與 `--no-save-model` 選項（預設行為不變），保留 v1 實驗檔案並以 `v2_` 前綴輸出新版結果至 `experiments/results/e4_v2_*.csv` 與對應圖表。
  - 將 `data/features/features_v2.csv` 與 `labels.csv` 以 `["song", "singer_id"]` 一對一合併為 `data/features/all_v2.csv`（132 筆、0 缺失值），並沿用原本 10 個特徵完成新舊版 LOSO 對照（見下方筆記「v1 vs. v2 模型比較結果」）。
  - 完成 `v2` Overall 四組特徵消融（`--drop-group`）與「排除 `singer_id == 0`（$n=126$）」對照分析，確認目前正面 $\rho$ 主要來自「偏離低分 Singer 0」的反轉關聯，而非真正學會歌唱品質。
  - 以 v2 模型執行 `python tests/simulate_singing.py`，確認分數排序倒置（正常唱 `31`、偏高半音 `33`、拖拍 350ms `39`、亂唱 `81`）；驗證規則式降級在現行程式下仍正常通過（正常唱 `95`、偏高半音 `55`、拖拍 350ms `71`、亂唱 `21`）。

## 卡住／需要別人

- **需要 #5 確認 M2 參考旋律調整方向（關鍵發現）**：
  - 檢查 `labels.csv` 發現，`singer_id = 0` 在 6 首歌的 `overall_performance` 僅 **`1.50`–`3.00`**（平均 `2.125`、`pitch` 僅 `1.50`–`2.00`）。
  - 因為 `features.csv` 與 `features_v2.csv` 皆以 Singer 0 當代理參考旋律，造成高分歌手（`>= 9.0`）的特徵誤差反而比中低分歌手更大，使 `contour.interval_accuracy`（$\rho = -0.435$）、`contour.note_coverage`（$\rho = -0.442$）與評分呈負相關，`rhythm.median_abs_onset_ms`（$\rho = +0.346$）呈正相關。
  - 此問題導致訓練出的模型在真實／合成唱段上給分倒置（亂唱分數最高），建議依 `PROJECT_PLAN.md` 11/29 檢查點討論是否改用原曲人聲參考或高分歌手備案（注意避免將當作參考的歌手放入訓練／評估）。
- **需要 #4 知會整合狀態**：v2 模型因上述資料特徵問題仍未通過 `simulate_singing.py` 行為檢查；整合 Demo 時請維持規則式 fallback（本機不放 `models/*.joblib` 即可），不要將目前模型用於現場 Demo 給分。
- **等待全組自錄資料（預計 12/01–12/04）**：自錄 trace 收齊後，會依據各條件測試結果微調 `scorer.py` 中 `make_tips()` 的文字建議門檻與內容。

## 筆記

### 1. v1 vs. v2 模型比較結果（132 筆，沿用原本 10 個特徵）

| 目標 | 版本 | Pitch-only $\rho$ | Ridge $\rho$ (95% CI) | Ridge MAE | RF $\rho$ (95% CI) | RF MAE |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `overall` | v1 | 0.039 | 0.372 [0.20, 0.53] | 1.686 | 0.283 [0.11, 0.46] | 1.735 |
| `overall` | **v2** | **0.120** | **0.437** [0.28, 0.58] | **1.576** | **0.470** [0.31, 0.62] | **1.540** |
| `pitch` | v1 | 0.062 | 0.362 [0.18, 0.52] | **1.646** | 0.315 [0.14, 0.48] | 1.684 |
| `pitch` | **v2** | **0.089** | **0.398** [0.24, 0.55] | 1.689 | **0.430** [0.27, 0.58] | **1.660** |
| `rhythm` | v1 | 0.028 | 0.321 [0.13, 0.48] | 1.706 | 0.259 [0.09, 0.43] | 1.745 |
| `rhythm` | **v2** | **0.070** | **0.410** [0.24, 0.56] | **1.689** | **0.442** [0.28, 0.59] | **1.609** |
| `expression` | v1 | -0.045 | **0.399** [0.23, 0.55] | **1.807** | 0.310 [0.13, 0.47] | 1.819 |
| `expression` | **v2** | **0.023** | 0.357 [0.20, 0.51] | 1.850 | **0.404** [0.24, 0.56] | **1.679** |

Overall 特徵消融（Ridge / RF pooled $\rho$）：

| 特徵組別 | v1 Ridge / RF | v2 Ridge / RF |
| --- | --- | --- |
| 完整 10 特徵 | 0.372 / 0.283 | 0.437 / 0.470 |
| 去 `pitch` | 0.364 / 0.263 | 0.414 / 0.448 |
| 去 `rhythm` | 0.375 / 0.336 | **0.453 / 0.523** |
| 去 `contour` | 0.174 / 0.196 | 0.315 / 0.326 |
| 去 `expression` | 0.366 / 0.252 | 0.438 / 0.459 |

- **現象解讀**：v2 在數據指標（LOSO $\rho$ 與 MAE）整體優於 v1，但拿掉 `rhythm` 後表現反而最高（`0.453` / `0.523`），且排除 `singer_id == 0`（$n=126$）後 `overall` 的 Pitch-only $\rho$ 降至 `-0.004`、Ridge 降至 `0.378`。主要受限於 Singer 0（低分歌手）代理參考導致特徵方向與評分相反，相關證據已保留於 `experiments/results/e4_v2_*.csv` 供 E4 報告分析與後續特徵修正參考。

### 2. Acapella `song1`–`song6` 對應歌名（給 #5 與選歌參考）
- `song1`：但願人長久
- `song2`：我只在乎你
- `song3`：甜蜜蜜
- `song4`：如果沒有你
- `song5`：至少還有你
- `song6`：月亮代表我的心

(他們真的很愛鄧麗君欸)

### 3. 資料集讀取與合併方式（給 #5 參考）
- **資料結構**：Acapella 為同一批 22 位歌手（`singer_id` 0–21）各唱完 6 首歌，共 132 筆；合併特徵表時以 `["song", "singer_id"]` 作為主鍵進行 merge 即可。
- **套件踩坑**：Hugging Face 下載的資料夾為各自獨立的 `.arrow` 快取檔，需用 `Dataset.from_file()` 讀取；此外新版 `datasets` 讀取時會觸發 `torchcodec` 與 `Pillow` 解碼錯誤，處理前需先移除 `Image` 欄位並設定 `Audio(decode=False)`。

### 4. 標籤分布觀察（給 #5 特徵設計與 E4 實驗參考）
- **雙峰極端分布**：所有評分面向皆呈兩群分離——一般演唱者集中在 `1.0–6.0` 分，`6.5–8.5` 分幾乎空白，專業參考歌手集中在 `9.5–10.0` 分（每首歌約 3–4 筆）。
- **表現力給分最嚴格**：`pitch`（平均 $5.25$）與 `rhythm`（平均 $5.12$）的一般群組多集中在 4–6 分；`expression`（定義為 `(vibrato + dynamic) / 2`）平均僅 $4.04$，一般群組多落在 2–4 分。
- **跨歌分布一致**：`song1` 到 `song6` 的中位數與四分位距（IQR）相當穩定，沒有單一歌曲給分特別鬆或特別嚴的偏差，適合進行 Leave-One-Song-Out（LOSO）交叉驗證。

### 5. 訓練與後端推論管線說明（給 #4 整合與 Demo 備案參考）
- **多目標訓練指令**：`python scoring/train.py data/features/all_v2.csv --target <overall|pitch|rhythm|expression> --prefix v2_` 會自動對應欄位並輸出 `models/<target>.joblib`，同時將評估數據與散佈圖存至 `experiments/results/`。
- **後端自動降級機制**：`scorer.py` 會個別檢查 `models/overall.joblib`、`pitch.joblib`、`rhythm.joblib`、`expression.joblib` 是否存在；存在的面向用模型預測，不存在的面向（包含無標籤的 `contour`）自動維持規則式給分，Demo 時若需退回純規則式只需清空 `models/` 即可。
