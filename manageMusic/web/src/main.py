import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

DB_PATH = os.getenv("DB_PATH", "/data/manage_music.db")
DATA_DIR = Path(DB_PATH).parent
FILES_DIR = DATA_DIR / "files"
DATA_DIR.mkdir(parents=True, exist_ok=True)
FILES_DIR.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Music (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            url TEXT NOT NULL,
            file_hash TEXT,
            added_by_user_id TEXT NOT NULL,
            added_by_display_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_music_url ON Music(url)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_music_file_hash"
        " ON Music(file_hash) WHERE file_hash IS NOT NULL"
    )
    conn.commit()
    conn.close()


init_db()

app = FastAPI(title="manageMusic Web UI")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    conn = get_conn()
    songs = conn.execute(
        "SELECT id, title, artist, url, added_by_display_name, created_at"
        " FROM Music ORDER BY datetime(created_at) DESC, id DESC"
    ).fetchall()
    conn.close()
    return templates.TemplateResponse(
        "index.html", {"request": request, "songs": songs}
    )


@app.get("/files/{name}")
async def get_file(name: str) -> FileResponse:
    if name != Path(name).name:
        raise HTTPException(status_code=400, detail="invalid name")
    target = FILES_DIR / name
    if not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(str(target))


@app.post("/delete/{song_id}")
async def delete_song(song_id: int) -> RedirectResponse:
    conn = get_conn()
    row = conn.execute(
        "SELECT url FROM Music WHERE id = ?", (song_id,)
    ).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="song not found")
    conn.execute("DELETE FROM Music WHERE id = ?", (song_id,))
    conn.commit()
    conn.close()

    url = row["url"]
    if url.startswith("/files/"):
        name = Path(url[len("/files/"):]).name
        target = FILES_DIR / name
        if target.is_file():
            target.unlink(missing_ok=True)

    return RedirectResponse(url="/", status_code=303)
