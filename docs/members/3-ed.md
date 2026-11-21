# #3 ed：評分模型與建議

> 最後更新：2026-11-21

## 目前在做

- branch：`three`
- 內容：已完成 Acapella 資料集整理，並提前完成 `scoring/train.py`（修改 D）與 `scoring/scorer.py`（修改 E）的程式升級；準備發 PR 合併進 `main`，等待 #5 的真實特徵檔進行正式訓練與 E4 實驗。

## 本週目標（對照 PROJECT_PLAN.md）

- [x] 下載 Acapella 資料集，整理 132 筆 × 9 面向分數成 `data/datasets/acapella/labels.csv`
- [x] 聽出 `song1`–`song6` 的真實歌名並回報群組（供 #5 找原曲與全組選 Demo 歌）
- [x] 繪製分數分布圖並整理資料檢視筆記
- [x] 跑通 `python scoring/train.py --demo` 熟悉現有訓練管線
- [x] 改寫 `scoring/train.py`（支援 `--target`、`--drop-group`、雙指標 Spearman $\rho$、Bootstrap 95% CI 與自動輸出結果圖表）
- [x] 改寫 `scoring/scorer.py`（支援自動偵測並載入 `overall`、`pitch`、`rhythm`、`expression` 模型，無模型時自動退回規則式）
- [ ] 跑完 `tests/simulate_singing.py` 迴歸測試並發 PR 合併進 `main`

## 已完成

- 2026-11-21：跑通 `scoring/train.py --demo` 確認原始訓練流程（Ridge LOSO 驗證 Spearman $\rho = 0.923$、$\text{MAE} = 0.374$）。
- 2026-11-21：合併 Hugging Face Acapella 6 個 split（共 132 筆）輸出 `data/datasets/acapella/labels.csv`，並匯出試聽檔辨識出 6 首歌名。
- 2026-11-21：產出四大目標（`overall_performance`、`pitch`、`rhythm`、`expression`）的統計摘要與分布圖（`score_distributions.png`、`score_by_song_boxplot.png`）。
- 2026-11-21：完成 `scoring/train.py` 升級（W2 修改 D）並以 `--demo` 模式測通多目標訓練、特徵消融與 `experiments/results/` 圖表輸出。
- 2026-11-21：完成 `scoring/scorer.py` 升級（W3 修改 E），後端現已支援依 `models/<target>.joblib` 切換各面向模型給分。

## 卡住／需要別人

- **等待 #5（預計 11/29 M2）**：需要 6 首歌的 `features.csv` 才能與 `labels.csv` 合併進行正式模型訓練與 E4 實驗（請 #5 確認輸出 CSV 包含 `song` 與 `singer_id` 兩欄方便 merge）。
- **等待全組自錄資料（預計 12/01–12/04）**：自錄 trace 收齊後，會依據各條件測試結果微調 `scorer.py` 中 `make_tips()` 的文字建議門檻與內容。

## 筆記

### 1. Acapella `song1`–`song6` 對應歌名（給 #5 與選歌參考）
- `song1`：但願人長久
- `song2`：我只在乎你
- `song3`：甜蜜蜜
- `song4`：如果沒有你
- `song5`：至少還有你
- `song6`：月亮代表我的心

(他們真的很愛鄧麗君欸)

### 2. 資料集讀取與合併方式（給 #5 參考）
- **資料結構**：Acapella 為同一批 22 位歌手（`singer_id` 0–21）各唱完 6 首歌，共 132 筆；合併特徵表時以 `["song", "singer_id"]` 作為主鍵進行 merge 即可。
- **套件踩坑**：Hugging Face 下載的資料夾為各自獨立的 `.arrow` 快取檔，需用 `Dataset.from_file()` 讀取；此外新版 `datasets` 讀取時會觸發 `torchcodec` 與 `Pillow` 解碼錯誤，處理前需先移除 `Image` 欄位並設定 `Audio(decode=False)`。

### 3. 標籤分布觀察（給 #5 特徵設計與 E4 實驗參考）
- **雙峰極端分布**：所有評分面向皆呈兩群分離——一般演唱者集中在 `1.0–6.0` 分，`6.5–8.5` 分幾乎空白，專業參考歌手集中在 `9.5–10.0` 分（每首歌約 3–4 筆）。
- **表現力給分最嚴格**：`pitch`（平均 $5.25$）與 `rhythm`（平均 $5.12$）的一般群組多集中在 4–6 分；`expression`（定義為 `(vibrato + dynamic) / 2`）平均僅 $4.04$，一般群組多落在 2–4 分。
- **跨歌分布一致**：`song1` 到 `song6` 的中位數與四分位距（IQR）相當穩定，沒有單一歌曲給分特別鬆或特別嚴的偏差，適合進行 Leave-One-Song-Out（LOSO）交叉驗證。

### 4. 訓練與後端推論管線說明（給 #4 整合與 Demo 備案參考）
- **多目標訓練指令**：`python scoring/train.py data/features/all.csv --target <overall|pitch|rhythm|expression>` 會自動對應欄位並輸出 `models/<target>.joblib`，同時將評估數據與散佈圖存至 `experiments/results/`。
- **後端自動降級機制**：`scorer.py` 會個別檢查 `models/overall.joblib`、`pitch.joblib`、`rhythm.joblib`、`expression.joblib` 是否存在；存在的面向用模型預測，不存在的面向（包含無標籤的 `contour`）自動維持規則式給分，Demo 時若需退回純規則式只需清空 `models/` 即可。