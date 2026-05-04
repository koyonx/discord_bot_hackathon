import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

DB_PATH = os.getenv("DB_PATH", "/data/manage_music.db")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            added_by_user_id TEXT NOT NULL,
            added_by_display_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
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
        " FROM songs ORDER BY datetime(created_at) DESC, id DESC"
    ).fetchall()
    conn.close()
    return templates.TemplateResponse(
        "index.html", {"request": request, "songs": songs}
    )


@app.post("/delete/{song_id}")
async def delete_song(song_id: int) -> RedirectResponse:
    conn = get_conn()
    cur = conn.execute("DELETE FROM songs WHERE id = ?", (song_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="song not found")
    return RedirectResponse(url="/", status_code=303)
