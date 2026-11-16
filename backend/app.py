"""後端伺服器（負責人：#5、#3）。

同時提供：
- 網頁（frontend/）
- 歌曲檔案（data/songs/<id>/song.json、accompaniment.wav）
- API：GET /api/songs、POST /api/score

啟動：uvicorn backend.app:app --reload --port 8000
然後打開 http://localhost:8000
（一定要用 localhost，瀏覽器才允許使用麥克風）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.features import extract_features  # noqa: E402
from scoring.scorer import score  # noqa: E402

SONGS = ROOT / "data" / "songs"
TRACES = ROOT / "data" / "traces"
app = FastAPI(title="Smart Karaoke")


class Frame(BaseModel):
    t: float
    f0_hz: float | None = None
    midi: float | None = None
    voiced: bool = False
    rms: float = 0.0


class Trace(BaseModel):
    song: str
    offset_ms: float = 0.0
    strict: bool = True
    frames: list[Frame]


@app.get("/api/songs")
def list_songs():
    out = []
    for d in sorted(SONGS.glob("*/song.json")):
        meta = json.loads(d.read_text(encoding="utf-8"))
        out.append({"id": d.parent.name, "title": meta.get("title", d.parent.name)})
    return out


@app.post("/api/score")
def score_trace(trace: Trace):
    path = SONGS / trace.song / "song.json"
    if not path.exists():
        raise HTTPException(404, f"找不到歌曲 {trace.song}")
    song = json.loads(path.read_text(encoding="utf-8"))
    frames = [f.model_dump() for f in trace.frames]

    # 每次演唱都存下來：之後可當作實驗資料（#3、#6 會用到）
    TRACES.mkdir(parents=True, exist_ok=True)
    n = len(list(TRACES.glob(f"{trace.song}_*.json")))
    (TRACES / f"{trace.song}_{n:03d}.json").write_text(trace.model_dump_json(), encoding="utf-8")

    feats = extract_features(song, frames, offset_ms=trace.offset_ms)
    result = score(feats, strict=trace.strict)
    result["per_note"] = feats["per_note"]
    return result


app.mount("/songs", StaticFiles(directory=SONGS), name="songs")
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
