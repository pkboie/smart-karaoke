# #3 ed：評分模型與建議

> 最後更新：2026-11-28

## 目前在做

- branch：`model/acapella-e4`（已同步至 `b43b1d9`）
- 內容：已完成 #5 探索版高分代理參考資料集（`data/features/features_v3_experimental.csv`）的合併、LOSO／Ablation 比較、去參考歌手（$n=126$）對照、單變量相關性檢查，以及 `tests/simulate_singing.py` 行為驗證。

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
- [x] 合併 `features_v2.csv` 與 `labels.csv`（`data/features/all_v2.csv`），完成 v1 vs. v2 比較並定位 Singer 0 低分偏差
- [x] 合併 `features_v3_experimental.csv` 與 `labels.csv`（`data/features/all_v3_experimental.csv`），驗證高分代理參考下的特徵方向與模型行為
- [ ] 待取得「無標籤洩漏」的正式參考特徵（例如原曲人聲參考）並解決 `expression.vibrato_cents`／`key_shift` 問題後重跑 E4 定稿；自錄後微調 `make_tips()`

## 已完成

- 2026-11-21：跑通 `scoring/train.py --demo` 確認原始訓練流程（Ridge LOSO 驗證 Spearman $\rho = 0.923$、$\text{MAE} = 0.374$）。
- 2026-11-21：合併 Hugging Face Acapella 6 個 split（共 132 筆）輸出 `data/datasets/acapella/labels.csv`，並匯出試聽檔辨識出 6 首歌名。
- 2026-11-21：產出四大目標（`overall_performance`、`pitch`、`rhythm`、`expression`）的統計摘要與分布圖（`score_distributions.png`、`score_by_song_boxplot.png`）。
- 2026-11-21：完成 `scoring/train.py` 升級（W2 修改 D）並以 `--demo` 模式測通多目標訓練、特徵消融與 `experiments/results/` 圖表輸出。
- 2026-11-21：完成 `scoring/scorer.py` 升級（W3 修改 E），後端現已支援依 `models/<target>.joblib` 切換各面向模型給分。
- 2026-11-24：將 `data/features/features.csv` 與 `labels.csv` 以 `song`、`singer_id` 一對一合併，共 132 筆；修正 `train.py` 僅選取 `pitch.*`、`rhythm.*`、`contour.*`、`expression.*` 欄位，排除標籤洩漏。v1 Overall Ridge LOSO Spearman $\rho=0.372$、MAE $=1.686$。
- 2026-11-28：
  - 為 `scoring/train.py` 新增 `--prefix` 與 `--no-save-model` 選項（預設行為不變），保留 v1 實驗檔案並以 `v2_` 前綴輸出新版結果至 `experiments/results/e4_v2_*.csv` 與對應圖表。
  - 完成 `features_v2.csv` 與 `labels.csv` 合併（`data/features/all_v2.csv`）及 v1 vs. v2 對照，定位出 `singer_id = 0`（`overall_performance` 平均僅 `2.125`）造成特徵與評分方向反轉、v2 模型在 `tests/simulate_singing.py` 給分倒置（正常唱 `31` < 亂唱 `81`）。
  - 合併 #5 探索版高分代理參考 `features_v3_experimental.csv` 與 `labels.csv` 為 `data/features/all_v3_experimental.csv`，以 `--prefix v3_exp_` 完成四目標 LOSO、Ablation、去參考歌手（$n=126$）與單變量相關性驗證（見下方筆記「v1 vs. v2 vs. v3（探索版）比較」）。
  - **關鍵改善**：v3 特徵與人評的相關方向全部轉為合理方向，Pitch-only baseline 由 v1 `0.039`／v2 `0.120` 提升至 **`0.243`**（去參考歌手後仍由 v2 `-0.004` 升為 **`+0.129`**）；在 `tests/simulate_singing.py` 中，v3 模型分數排序不再倒置（正常唱 `93` > 拖拍 350ms `75` > 亂唱 `60`）。
  - **尚存問題**：(1) `v3_README.txt` 已明載此版以測試曲標籤選高分歌手當參考，有標籤洩漏、不可作為最終無偏 E4 成績；(2) `bd68932` 修改 `scoring/features.py` 套用 `key_shift` 補償後，整首「偏高半音」會被自動移調校正而不扣音準分（v3 模型：`93` 分；規則式 fallback 同樣由原本 `55` 變成 `95`、`亂唱` `18`）；(3) `expression.vibrato_cents` 與人評仍呈負相關（$-0.216$）。

## 卡住／需要別人

- **需要 #5 協助（接續 v3 實驗的下一步）**：
  - 目前 v3 已驗證「高品質參考旋律＋`usr_aligned`／八度折疊修正」確實能讓所有音準／節奏／走向特徵方向轉正。但因 v3 選參考歌手時看過測試曲人類評分（即使拿掉該 6 筆參考歌手仍屬標籤洩漏），**正式 E4 仍需要無標籤洩漏的參考來源**（例如正式原曲分離人聲 `song2`／`song6` 或不看標籤的參考選擇）。
  - `scoring/features.py` 套用 `key_shift` 後，整首偏高半音會被自動移調而不扣音準分（無論模型或規則式都可能受影響），需共同確認伴奏播放下的 Demo 是否應懲罰非預期移調，或僅在 Acapella 清唱比較時啟用移調補償。
  - `expression.vibrato_cents`（標準差）仍會被走音晃動拉高（一般群平均 `107.4` vs. 參考歌手 `29.3`，與評分 $\rho=-0.216$），支持按 W3 計畫改為 4–8 Hz 顫音頻帶能量。
- **需要 #4 知會整合狀態**：已清空本機測試產生的探索版 `models/*.joblib`；Demo 整合請維持無模型規則式 fallback，但需留意 `bd68932` 修改 `scoring/features.py` 對「整首偏高半音」的給分影響。
- **等待全組自錄資料（預計 12/01–12/04）**：自錄 trace 收齊後，會依據各條件測試結果微調 `scorer.py` 中 `make_tips()` 的文字建議門檻與內容。

## 筆記

### 1. v1 vs. v2 vs. v3（探索版，有參考選擇洩漏）模型比較（沿用 10 個特徵）

| 目標 | 版本 | Pitch-only $\rho$ | Ridge $\rho$ (95% CI) | Ridge MAE | RF $\rho$ (95% CI) | RF MAE |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `overall` | v1 | 0.039 | 0.372 [0.20, 0.53] | 1.686 | 0.283 [0.11, 0.46] | 1.735 |
| `overall` | v2 | 0.120 | **0.437** [0.28, 0.58] | **1.576** | **0.470** [0.31, 0.62] | **1.540** |
| `overall` | v3 (exp) | **0.243** | 0.318 [0.13, 0.48] | 1.593 | 0.442 [0.28, 0.59] | 1.561 |
| `pitch` | v1 | 0.062 | 0.362 [0.18, 0.52] | 1.646 | 0.315 [0.14, 0.48] | 1.684 |
| `pitch` | v2 | 0.089 | **0.398** [0.24, 0.55] | 1.689 | 0.430 [0.27, 0.58] | 1.660 |
| `pitch` | v3 (exp) | **0.173** | 0.369 [0.18, 0.52] | **1.635** | **0.478** [0.32, 0.62] | **1.629** |
| `rhythm` | v1 | 0.028 | 0.321 [0.13, 0.48] | 1.706 | 0.259 [0.09, 0.43] | 1.745 |
| `rhythm` | v2 | 0.070 | **0.410** [0.24, 0.56] | 1.689 | 0.442 [0.28, 0.59] | 1.609 |
| `rhythm` | v3 (exp) | **0.203** | 0.331 [0.15, 0.48] | **1.611** | **0.449** [0.29, 0.59] | **1.554** |
| `expression` | v1 | -0.045 | **0.399** [0.23, 0.55] | 1.807 | 0.310 [0.13, 0.47] | 1.819 |
| `expression` | v2 | 0.023 | 0.357 [0.20, 0.51] | 1.850 | **0.404** [0.24, 0.56] | **1.679** |
| `expression` | v3 (exp) | **0.164** | 0.375 [0.20, 0.52] | **1.607** | 0.359 [0.18, 0.51] | 1.710 |

- **去參考歌手對照（$n=126$）**：v3 排除 6 筆參考歌手後，`overall` Ridge $\rho = 0.212$、RF $\rho = 0.328$；`pitch` RF $\rho = 0.405$（`0.22`–`0.56`）；`rhythm` RF $\rho = 0.372$。雖然絕對 $\rho$ 因移除「偏離低分 Singer 0」的反轉假象而比 v2 低，但單變量方向全面轉正：
  - `pitch.median_abs_cents`：v2 `+0.098` → v3 `-0.247`（去參考 `-0.136`）
  - `pitch.hit_rate_50c`：v2 `-0.107` → v3 `+0.273`（去參考 `+0.165`）
  - `rhythm.median_abs_onset_ms`：v2 `+0.346` → v3 `-0.350`（去參考 `-0.253`）
  - `contour.interval_accuracy`：v2 `-0.435` → v3 `+0.425`（去參考 `+0.340`）
  - `contour.note_coverage`：v2 `-0.442` → v3 `+0.407`（去參考 `+0.320`）
- **v3 Overall Ablation（Ridge / RF pooled $\rho$）**：完整 `0.318 / 0.442`｜去 `pitch` `0.327 / 0.418`｜去 `rhythm` `0.359 / 0.426`｜去 `contour` `0.312 / 0.434`｜去 `expression` `0.346 / 0.385`（在 RF 上四組移除皆下降，且移除 `expression` 掉最多：`0.442 → 0.385`）。
- **行為驗證（`tests/simulate_singing.py`）**：
  - v1 模型：正常 `11`、偏高 `12`、拖拍 `31`、亂唱 `13`
  - v2 模型：正常 `31`、偏高 `33`、拖拍 `39`、亂唱 `81`
  - **v3 探索模型**：正常 `93`、偏高 `93`、拖拍 `75`、亂唱 `60`

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
- **多目標訓練指令**：`python scoring/train.py data/features/all_v3_experimental.csv --target <overall|pitch|rhythm|expression> --prefix v3_exp_` 會自動對應欄位並輸出 `models/<target>.joblib`，同時將評估數據與散佈圖存至 `experiments/results/`。
- **後端自動降級機制**：`scorer.py` 會個別檢查 `models/overall.joblib`、`pitch.joblib`、`rhythm.joblib`、`expression.joblib` 是否存在；存在的面向用模型預測，不存在的面向（包含無標籤的 `contour`）自動維持規則式給分，Demo 時若需退回純規則式只需清空 `models/` 即可。
