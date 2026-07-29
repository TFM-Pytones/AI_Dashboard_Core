"""Issue #13 — Integración API de YouTube.

Busca vídeos relacionados con turismo en Tenerife y descarga sus comentarios,
cargándolos en raw_data.youtube_videos / raw_data.youtube_comments (Neon).

Requiere YOUTUBE_API_KEY en el .env (ver README de esta carpeta / .env.example).
"""

import os
import sys
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
API_BASE = "https://www.googleapis.com/youtube/v3"

SEARCH_TERMS = [
    "Tenerife turismo",
    "Tenerife travel",
    "visitar Tenerife",
    "Tenerife vacaciones",
]

MAX_VIDEOS_PER_TERM = 15
MAX_COMMENT_PAGES_PER_VIDEO = 3  # ~300 comentarios por vídeo como mucho


def get_db_connection():
    return psycopg2.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        port="5432",
        sslmode="require",
    )


def ensure_schema(conn):
    schema_path = Path(__file__).resolve().parents[2] / "sql" / "youtube_schema.sql"
    with conn.cursor() as cur:
        cur.execute(schema_path.read_text())
    conn.commit()


def search_videos(term: str) -> list[dict]:
    """search.list cuesta 100 unidades de cuota por llamada — usar con moderación."""
    params = {
        "key": YOUTUBE_API_KEY,
        "q": term,
        "part": "snippet",
        "type": "video",
        "maxResults": MAX_VIDEOS_PER_TERM,
        "relevanceLanguage": "es",
        "regionCode": "ES",
    }
    resp = requests.get(f"{API_BASE}/search", params=params, timeout=30)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return [
        {
            "video_id": it["id"]["videoId"],
            "search_term": term,
            "title": it["snippet"]["title"],
            "channel_title": it["snippet"]["channelTitle"],
            "published_at": it["snippet"]["publishedAt"],
        }
        for it in items
    ]


def fetch_view_counts(video_ids: list[str]) -> dict[str, int]:
    """videos.list cuesta solo 1 unidad por llamada (hasta 50 ids de golpe)."""
    if not video_ids:
        return {}
    params = {"key": YOUTUBE_API_KEY, "id": ",".join(video_ids), "part": "statistics"}
    resp = requests.get(f"{API_BASE}/videos", params=params, timeout=30)
    resp.raise_for_status()
    return {
        it["id"]: int(it["statistics"].get("viewCount", 0))
        for it in resp.json().get("items", [])
    }


def fetch_comments(video_id: str) -> list[dict]:
    """commentThreads.list cuesta solo 1 unidad por llamada — se puede paginar."""
    comments = []
    page_token = None
    for _ in range(MAX_COMMENT_PAGES_PER_VIDEO):
        params = {
            "key": YOUTUBE_API_KEY,
            "videoId": video_id,
            "part": "snippet",
            "maxResults": 100,
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get(f"{API_BASE}/commentThreads", params=params, timeout=30)
        if resp.status_code == 403:
            # Comentarios desactivados en el vídeo: no es un error del script.
            break
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append(
                {
                    "comment_id": item["snippet"]["topLevelComment"]["id"],
                    "video_id": video_id,
                    "author": top.get("authorDisplayName"),
                    "text": top.get("textDisplay"),
                    "like_count": top.get("likeCount", 0),
                    "published_at": top.get("publishedAt"),
                }
            )

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return comments


def save_videos(conn, videos: list[dict]):
    if not videos:
        return
    with conn.cursor() as cur:
        for v in videos:
            cur.execute(
                """
                INSERT INTO bronze.youtube_videos
                    (video_id, search_term, title, channel_title, published_at, view_count)
                VALUES (%(video_id)s, %(search_term)s, %(title)s, %(channel_title)s, %(published_at)s, %(view_count)s)
                ON CONFLICT (video_id) DO UPDATE SET
                    view_count = EXCLUDED.view_count,
                    fetched_at = now()
                """,
                v,
            )
    conn.commit()


def save_comments(conn, comments: list[dict]):
    if not comments:
        return
    with conn.cursor() as cur:
        for c in comments:
            cur.execute(
                """
                INSERT INTO bronze.youtube_comments
                    (comment_id, video_id, author, text, like_count, published_at)
                VALUES (%(comment_id)s, %(video_id)s, %(author)s, %(text)s, %(like_count)s, %(published_at)s)
                ON CONFLICT (comment_id) DO NOTHING
                """,
                c,
            )
    conn.commit()


def main():
    if not YOUTUBE_API_KEY:
        print("Falta YOUTUBE_API_KEY en el .env. Revisa .env.example.")
        sys.exit(1)

    conn = get_db_connection()
    ensure_schema(conn)

    total_videos, total_comments = 0, 0
    for term in SEARCH_TERMS:
        print(f"Buscando: {term!r}...")
        videos = search_videos(term)
        view_counts = fetch_view_counts([v["video_id"] for v in videos])
        for v in videos:
            v["view_count"] = view_counts.get(v["video_id"], 0)
        save_videos(conn, videos)
        total_videos += len(videos)

        for v in videos:
            comments = fetch_comments(v["video_id"])
            save_comments(conn, comments)
            total_comments += len(comments)

    print(f"Hecho: {total_videos} vídeos, {total_comments} comentarios guardados.")
    conn.close()


if __name__ == "__main__":
    main()
