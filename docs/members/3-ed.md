# #3 ed：評分模型與建議

> 最後更新：2026-11-24

## 目前在做

- branch：`model/acapella-e4`
- 內容：已用 #5 的 132 筆 Acapella 特徵完成初步 E4；發現合併標籤後，`train.py` 把裸欄位 `pitch`、`rhythm` 等標籤誤當特徵，造成目標洩漏與後端 `KeyError: 'pitch'`。已修正特徵欄位篩選並重新訓練；目前 E4 結果偏弱，需先檢查特徵品質與模型在 demo 上的行為，再送 PR。

## 本週目標（對照 PROJECT_PLAN.md）

- [x] 下載 Acapella 資料集，整理 132 筆 × 9 面向分數成 `data/datasets/acapella/labels.csv`
- [x] 聽出 `song1`–`song6` 的真實歌名並回報群組（供 #5 找原曲與全組選 Demo 歌）
- [x] 繪製分數分布圖並整理資料檢視筆記
- [x] 跑通 `python scoring/train.py --demo` 熟悉現有訓練管線
- [x] 改寫 `scoring/train.py`（支援 `--target`、`--drop-group`、雙指標 Spearman $\rho$、Bootstrap 95% CI 與自動輸出結果圖表）
- [x] 改寫 `scoring/scorer.py`（支援自動偵測並載入 `overall`、`pitch`、`rhythm`、`expression` 模型，無模型時自動退回規則式）
- [x] 合併 132 筆 features 與 labels，跑初步四目標 LOSO
- [x] 修正訓練欄位篩選，排除評分標籤造成的特徵洩漏
- [x] 無模型的規則式降級通過 `tests/simulate_singing.py`
- [ ] 用修正後特徵檢查 E4／ablation，確認 demo 模型分數行為，再發 PR

## 已完成

- 2026-11-21：跑通 `scoring/train.py --demo` 確認原始訓練流程（Ridge LOSO 驗證 Spearman $\rho = 0.923$、$\text{MAE} = 0.374$）。
- 2026-11-21：合併 Hugging Face Acapella 6 個 split（共 132 筆）輸出 `data/datasets/acapella/labels.csv`，並匯出試聽檔辨識出 6 首歌名。
- 2026-11-21：產出四大目標（`overall_performance`、`pitch`、`rhythm`、`expression`）的統計摘要與分布圖（`score_distributions.png`、`score_by_song_boxplot.png`）。
- 2026-11-21：完成 `scoring/train.py` 升級（W2 修改 D）並以 `--demo` 模式測通多目標訓練、特徵消融與 `experiments/results/` 圖表輸出。
- 2026-11-21：完成 `scoring/scorer.py` 升級（W3 修改 E），後端現已支援依 `models/<target>.joblib` 切換各面向模型給分。
- 2026-11-24：將 `data/features/features.csv` 與 `labels.csv` 以 `song`、`singer_id` 一對一合併，共 132 筆；首次訓練發現 `pitch`、`rhythm` 等標籤欄位混入特徵，造成先前 E4 結果虛高並讓模型推論時缺欄位。
- 2026-11-24：修正 `train.py` 僅選取 `pitch.*`、`rhythm.*`、`contour.*`、`expression.*` 欄位；重跑後 Overall Ridge LOSO Spearman $\rho=0.372$、MAE $=1.686$。此為初步結果，顯示目前特徵預測力有限，不應沿用先前有洩漏的成績。
- 2026-11-24：規則式降級下 `tests/simulate_singing.py` 通過；載入正式模型時雖不再崩潰，但合成 demo 歌的分數排序不符合預期，模型暫不適合 demo。

## 卡住／需要別人

- **需要 #5 協助確認特徵品質**：抽查 132 筆的特徵是否合理，尤其確認 Acapella 音檔與參考旋律的移調、起點對齊；目前 LOSO 成績遠低於有洩漏時的結果。另請維持 `song`、`singer_id` 主鍵及帶群組前綴的特徵欄位。
- **需要 #4 知會整合狀態**：修正後模型目前未通過合成 demo 的分數行為檢查；整合前請先保留規則式 fallback，不要把這批模型當成 demo 已驗收版本。
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