# #5：離線處理與特徵工程（Offline Pipeline & Feature Engineering）

> 最後更新：2026-11-22

## 目前在做

- branch：`feature/offline-pipeline`
- 內容：
  - 離線產生參考歌曲 `song.json`
  - 改善 DTW 音高與時間對齊
  - 從 Acapella Arrow 資料集提取音高、節奏、旋律輪廓及表現力特徵
  - 準備提供給 #3 的 ML 訓練資料

## 本週目標（對照 PROJECT_PLAN.md）

- [x] 完成 DTW 移調估計與初步測試
- [x] 支援直接從 Arrow 資料集讀取音訊
- [x] 完成六首歌曲、132 筆特徵提取
- [x] 確認 Features 與 #3 的 `labels.csv` 可正確合併
- [ ] 檢查特徵數值的合理性與代理參考旋律造成的偏差
- [ ] 確認兩首 Demo 歌曲並完成正式 `song.json` v1
- [ ] 分享 Features CSV 與參考資料給 #3
- [ ] 完成 PR 並交由 #4 審查

## 已完成

- 2026-11-22：
  - 改善 `scoring/features.py` 的 DTW 對齊，加入整體移調估計。
  - 修改 `scoring/extract_dataset.py`，支援直接讀取 Hugging Face Arrow 音訊。
  - 新增 `offline/build_arrow_references.py`，批次建立測試用代理參考旋律。
  - 成功處理 `song1`～`song6`，每首 22 位歌手，共 132 筆錄音。
  - 產生 10 個特徵，涵蓋 `pitch.*`、`rhythm.*`、`contour.*`、`expression.*`。
  - Features CSV 與 #3 提供的 `labels.csv` 使用 `song`、`singer_id` 合併，132 筆全部配對成功，無缺失值。
  - 完成 Git Commit：`473fb36`、`29cd54a`。

## 卡住／需要別人

- 需要全組確認兩首 Demo 歌曲，並提供對應的原曲音檔。
- 需要正式參考旋律，取代目前的代理參考旋律。
- 需要與 #3 確認訓練特徵的品質與後續 E6 ablation 評估。
- `data/` 不納入 Git，需要透過共用雲端硬碟分享 Features CSV 與必要資料。

## 筆記

### 1. Feature Extraction

主要流程：

`Arrow audio → pYIN → MIDI pitch → DTW → Feature Extraction → CSV`

相關檔案：

- `scoring/features.py`
- `scoring/extract_dataset.py`
- `offline/build_arrow_references.py`

### 2. 資料格式

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

### 3. 執行方式

從 Arrow 提取單首歌曲的特徵：

```bash
python scoring/extract_dataset.py --arrow-dir data/datasets/acapella_hf/song1 --song song1 --out data/features/song1.csv --method pyin
```

測試用代理參考旋律批次產生：

```bash
python offline/build_arrow_references.py
```

此腳本目前處理 `song2`～`song6`，並使用 `singer_id=0` 的錄音建立參考旋律；若輸出檔案已存在，不會覆蓋。

### 4. 已知限制

目前六首歌曲的參考旋律使用範例歌手或 `singer_id=0` 的錄音產生，並非正式標準答案。

因此 `singer_id=0` 的音準與節奏特徵可能明顯優於其他歌手，造成資料偏差。

現有 132 筆 Features **適合用來測試 ML 訓練流程，但尚未完成特徵品質驗證，不應直接當成正式模型效能評估結果。**

正式版本需要確認原曲參考旋律、DTW 對齊品質及特徵與人工評分的關係。