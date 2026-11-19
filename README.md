# Smart Karaoke System（ML 期末專案 Group 5）

更嚴謹的卡拉 OK 評分系統：網頁上跟著音準線唱歌，唱完得到音準、節奏、旋律走向、表現力的分數與建議。

這是 **starter 骨架**：整條流程已經能跑通（離線產生音準線 → 網頁即時唱歌 → 後端評分），
每個模組都是可以運作的最小版本，請各負責人在上面改進。

## 快速開始（5 分鐘）

```bash
# 1. 安裝套件（建議用 Python 3.10+，venv 或 conda 都可以）
pip install -r requirements.txt

# 2. 產生示範歌曲（合成的小星星，沒有版權問題）
python offline/make_demo_song.py

# 3. 測試評分：模擬正常唱、偏高半音、拖拍、亂唱，看分數有沒有對應下降
python tests/simulate_singing.py

# 4. 啟動伺服器
uvicorn backend.app:app --reload --port 8000
```

打開 **http://localhost:8000**（一定要用 localhost，瀏覽器才允許使用麥克風），**戴耳機**，按「開始唱」。

## 資料夾結構

```
frontend/      網頁：選歌、伴奏、捲動音準線、即時音高、結果頁
  main.js        ← 主要邏輯（#4 畫面、#6 判分、#1 收音、#2 延遲）
  vendor/        pitchy 音高偵測（已打包，demo 不需要網路）
backend/app.py FastAPI：提供網頁、歌曲檔、/api/songs、/api/score
offline/       離線處理
  make_song.py       原曲 → Demucs → 音高偵測 → 切音符 → song.json（#5）
  make_demo_song.py  產生示範歌曲
scoring/       評分
  pitch_utils.py     Hz/MIDI 換算、音高偵測、切音符
  features.py        DTW 對齊 + 四類特徵（#5）
  scorer.py          特徵 → 分數 + 建議（#3）
  extract_dataset.py 資料集錄音 → features.csv（#5 → #3）
  train.py           訓練評分模型、leave-one-song-out、和 baseline 比較（#3）
experiments/   Proposal 的三項實驗起點（#1、#2、#6）
tests/         模擬演唱測試
examples/      四種 JSON 的範例
data/          音檔與資料集（不進 git）
  songs/<id>/    song.json、accompaniment.wav、vocals.wav
  traces/        每次演唱自動存檔（之後可當實驗資料）
models/        訓練好的模型（overall.joblib 存在時，後端自動用它算總分）
```

## 資料格式（所有人照這個寫）

| 檔案 | 內容 | 範例 |
| --- | --- | --- |
| `song.json` | 歌曲資訊與參考音符 | `examples/song.json` |
| `trace.json` | 一次演唱的音高紀錄（前端 → 後端）| `examples/trace.json` |
| `features.json` | 四類特徵 | `examples/features.json` |
| `score.json` | 評分結果 | `examples/score.json` |

音高一律用 **MIDI 編號**（60 = 中央 C，+1 = 升半音），時間一律用**秒**。

## 加入一首真的歌（#5）

```bash
pip install demucs            # 第一次需要，會下載模型
python offline/make_song.py 原曲.mp3 --id song1 --title "歌名" --bpm 76
```

自動產生的音符**一定會有錯**（例如同音高連唱兩個字會被合併），請打開 `data/songs/song1/song.json`
手動修正，並補上 `lyric`。網頁重新整理後就會出現在選單。

## 各負責人的第一步

| # | 負責 | 從哪裡開始 | 本週目標（11/22 前）|
| --- | --- | --- | --- |
| 1 | 收音、VAD、伴奏處理 | `frontend/main.js` 的 `startMic`、`RMS_MIN` | 改成 AudioWorklet；更好的人聲偵測 |
| 2 | 延遲、效能 | `main.js` 的延遲補償欄位；`experiments/pitch_benchmark.py` | 設計延遲量測流程，量出實際延遲 |
| 3 | 評分模型、建議 | `scoring/scorer.py`、`scoring/train.py` | 下載 Acapella，跑 `python scoring/train.py --demo` 熟悉流程 |
| 4 | 前端 | `frontend/` 全部 | 改善畫面：歌詞列、結果頁、選歌頁 |
| 5 | 離線處理、特徵 | `offline/make_song.py`、`scoring/features.py` | **週三前**：2 首正式歌曲的 song.json |
| 6 | 即時判分、音高準確度 | `main.js` 的 `sample()`；`experiments/` | 逐音符判分改進；Pitch accuracy 實驗 |

## 已知限制（待改進）

- 切音符是規則式，同音高連唱會合併 → 手動修正，或訓練 onset 模型
- 前端用 `requestAnimationFrame` 取樣（約 60 次/秒），之後可改 AudioWorklet 更穩定
- 評分是規則式；`train.py` 訓練出模型後，總分會自動改用模型
- 表現力特徵很粗略（顫音幅度、音量變化）
- 一定要戴耳機，否則麥克風會收到伴奏

## Git 協作

完整流程見 **[docs/git_workflow.md](docs/git_workflow.md)**。重點：

- `master` 保持可以跑；每個人在自己的 branch 開發，用 Pull Request 合併
- 改到共用的資料格式（JSON 欄位）前，先在群組說
- `data/`、`models/`、`*.zip` 不要 commit（已在 `.gitignore`）
- 每個人的進度寫在 `docs/members/<編號>-<名字>.md`（格式見 `docs/members/_template.md`）
