# Git 工作流程

原則只有三條：

1. **`master` 永遠可以跑**：不直接在 `master` 上寫程式，一律開 branch → PR → owner merge。
2. **一個 branch 只做一件事**：做完就開 PR，不要一個 branch 拖兩週。
3. **音檔、資料集、模型不進 git**：`data/`、`models/`、`*.zip` 已經在 `.gitignore`，用雲端硬碟分享。

唯一例外：自己的狀態檔 `docs/members/<編號>-<名字>.md` 可以直接推 `master`（見第 ⑥ 節）。

---

## 0. 第一次（每人只做一次）

```bash
git clone https://github.com/pkboie/smart-karaoke.git
cd smart-karaoke

# Python 環境（放在專案內的 .venv，已被 .gitignore 忽略）
python3 -m venv .venv
source .venv/bin/activate            # Windows PowerShell：.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 確認跑得起來
python offline/make_demo_song.py
python tests/simulate_singing.py     # 正常唱高分、偏高扣音準、拖拍扣節奏、亂唱低分

# 設定自己的名字（commit 上會顯示）
git config user.name  "你的 GitHub 帳號"
git config user.email "你的 GitHub email"
```

資料集從雲端硬碟下載後，解壓到 `data/datasets/`：

```
data/datasets/
├─ acapella_hf/song1 … song6
├─ mir1k/MIR-1K/{Wavfile, PitchLabel, …}
└─ mir1k_sample/
```

最後建立自己的狀態檔（見第 ⑥ 節），用第一個 PR 送上來。

---

## ① 開始一個新功能

```bash
git checkout master
git pull                              # 拿最新的 master
git checkout -b pitch/mir1k-benchmark # 開自己的 branch
```

**Branch 命名**：`<領域>/<做什麼>`，全小寫、用 `-` 連接。

| # | 領域前綴 | 例子 |
| --- | --- | --- |
| 1 | `mic/` | `mic/vad`、`mic/audioworklet` |
| 2 | `latency/` | `latency/calibration`、`latency/benchmark-memory` |
| 3 | `model/` | `model/per-target`、`model/ablation` |
| 4 | `ui/` | `ui/result-page`、`ui/trace-label` |
| 5 | `offline/` | `offline/global-align`、`offline/preview-tool` |
| 6 | `pitch/` | `pitch/mir1k-benchmark`、`pitch/note-judging` |
| 共用 | `docs/`、`fix/` | `docs/workflow`、`fix/backend-mkdir` |

---

## ② 做事 + commit（重複）

```bash
git status                            # 先看改了哪些檔案
git add <檔案1> <檔案2>                # 指定檔案，不要用 git add . 或 git add -A
git commit -m "pitch: benchmark 加 --dataset mir1k"
git push -u origin pitch/mir1k-benchmark   # 第一次要加 -u，之後直接 git push
```

**Commit 訊息**：`<領域>: 做了什麼`，中英文都可以。一個 commit 做一件事，壞掉時比較好找。

**`git add` 之前一定要看 `git status`**。出現 `.wav`、`.zip`、`.arrow`、`.joblib`、`.venv/` 就停下來，不要加進去。

**每天收工前 push 一次**，就算還沒做完：電腦壞了不會丟東西，別人也看得到你的進度。

---

## ③ 隔天／做到一半重新開工

```bash
git checkout pitch/mir1k-benchmark
git fetch origin
git merge origin/master               # 把別人 merge 好的東西併進來
```

### 有 conflict 的時候

```bash
git status                            # 顯示 "both modified" 的就是衝突檔案
```

打開衝突檔案，會看到：

```
<<<<<<< HEAD
你的版本
=======
master 上的版本
>>>>>>> origin/master
```

改成正確的內容（可以兩邊都留），**把 `<<<<<<<`、`=======`、`>>>>>>>` 三行刪掉**，然後：

```bash
python tests/simulate_singing.py      # 確認合併後還能跑
git add <解完的檔案>
git commit                            # 用預設訊息 "Merge remote-tracking branch ..." 即可
git push
```

解不出來、或衝突的是別人負責的檔案：先 `git merge --abort` 回到合併前，再到群組找那個檔案的負責人一起解。

---

## ④ 做完 → 開 PR

**開 PR 前的檢查清單**

- [ ] 已經做過 ③（併入最新的 `master`），沒有衝突
- [ ] `python tests/simulate_singing.py` 結果沒有退步
- [ ] 改到前端／後端：`uvicorn backend.app:app --port 8000` 開網頁實際唱一次
- [ ] `git status` 沒有不該進 git 的檔案
- [ ] 改到共用的 JSON 欄位：已經先在群組說過
- [ ] 自己的狀態檔已更新

```bash
git push
```

到 GitHub 按「Compare & pull request」，base 選 `master`。PR 說明照這個格式寫：

```markdown
## 做了什麼
- benchmark 加 --dataset mir1k，答案改用 MIR-1K 人工標註

## 怎麼測
python experiments/pitch_benchmark.py --dataset mir1k --limit 10

## 結果 / 截圖
（數字、圖、畫面截圖）

## 需要別人注意的
- 新增 experiments/results/，結果 CSV 會放在這裡
```

PR 開了之後還可以繼續 `git push`，PR 會自動更新。

---

## ⑤ Owner merge 之後

```bash
git checkout master
git pull
git branch -d pitch/mir1k-benchmark   # 刪掉本機 branch
git push origin --delete pitch/mir1k-benchmark   # 刪掉遠端 branch（GitHub 上按過 Delete branch 就不用）
git fetch --prune                     # 清掉已經不存在的遠端 branch 紀錄
```

回到 ①，開下一個功能。

### Owner（#4）merge 的規則

- 用 **Squash and merge**：每個 PR 在 `master` 上變成一個 commit，歷史乾淨。
- merge 前看檢查清單有沒有勾完；有疑問直接在 PR 留言。
- merge 後在群組說一聲「已 merge XXX，大家 pull」。
- 12/10 功能凍結後，只 merge `fix/` 開頭的 PR。

---

## ⑥ 個人狀態檔 `docs/members/<編號>-<名字>.md`

每個人一個檔案，例如 `docs/members/6-pkboie.md`，格式照 `docs/members/_template.md`。內容包括：目前在做什麼、做完了什麼、卡在哪、需要誰。

**什麼時候更新**：每週三文字回報前，以及每次開 PR 時。

**每個人只改自己的檔案**，所以不會有衝突，可以直接推到 `master`：

```bash
git stash                             # 先把手上還沒 commit 的東西收起來
git checkout master
git pull
# 編輯 docs/members/6-pkboie.md
git add docs/members/6-pkboie.md
git commit -m "docs: 更新 #6 狀態"
git push
git checkout pitch/mir1k-benchmark    # 回到原本的 branch
git stash pop                         # 把收起來的東西拿回來
```

懶得切換 branch 的話，也可以在自己的 feature branch 裡改，跟著 PR 一起進 `master`。

---

## 常見狀況

| 狀況 | 怎麼辦 |
| --- | --- |
| 不小心在 `master` 上 commit 了（還沒 push） | `git branch my/feature` 把 commit 留到新 branch → `git reset --hard origin/master` → `git checkout my/feature` |
| `git pull` 說有本機修改會被覆蓋 | `git stash` → `git pull` → `git stash pop` |
| 不小心 `git add` 了大檔案（還沒 commit） | `git restore --staged <檔案>` |
| 大檔案已經 commit 了（還沒 push） | `git reset --soft HEAD~1` → `git restore --staged <檔案>` → 重新 commit |
| 大檔案已經 push 了 | 不要再動，馬上在群組找 owner 處理 |
| `git push` 被拒絕（`rejected ... fetch first`） | 別人推了同一個 branch：`git pull` 後再 `git push` |
| 想放棄某個檔案的所有修改 | `git restore <檔案>`（無法復原，先確定） |
| 不知道現在在哪個 branch | `git status` 第一行 |
