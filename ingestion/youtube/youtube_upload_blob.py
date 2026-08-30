"""Issue #13 — Integración API de YouTube.

Busca vídeos relacionados con turismo en Tenerife y descarga sus comentarios,
cargándolos en bronze-raw/youtube (Azure Blob Storage) como Parquet.

Requiere YOUTUBE_API_KEY y AZURE_STORAGE_CONNECTION_STRING en el .env (ver README de esta carpeta / .env.example).
"""

import os
import sys
import io
import argparse
import pandas as pd
from pathlib import Path

import requests
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError

load_dotenv(override=True)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
API_BASE = "https://www.googleapis.com/youtube/v3"
CONTAINER_NAME = "bronce-raw"

SEARCH_TERMS = [
    "Tenerife turismo",
    "Tenerife travel",
    "visitar Tenerife",
    "Tenerife vacaciones",
]

MAX_VIDEOS_PER_TERM = 15
MAX_COMMENT_PAGES_PER_VIDEO = 3  # ~300 comentarios por vídeo como mucho


def get_blob_client():
    if not AZURE_CONNECTION_STRING:
        print("Falta AZURE_STORAGE_CONNECTION_STRING en el .env.")
        sys.exit(1)
    return BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)


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


def upload_to_azure(blob_service_client, df_new: pd.DataFrame, blob_name: str, unique_key: str):
    if df_new.empty:
        return
        
    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
    
    # Intentar descargar el dataset existente para combinar y deduplicar
    df_combined = df_new
    try:
        downloader = blob_client.download_blob()
        existing_buffer = io.BytesIO(downloader.readall())
        df_existing = pd.read_parquet(existing_buffer)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    except ResourceNotFoundError:
        pass  # El blob no existe aún, se creará uno nuevo
    
    # Deduplicar quedándonos con la versión más reciente
    df_combined.drop_duplicates(subset=[unique_key], keep='last', inplace=True)
    
    # Subir a Azure
    parquet_buffer = io.BytesIO()
    df_combined.to_parquet(parquet_buffer, index=False)
    parquet_buffer.seek(0)
    blob_client.upload_blob(parquet_buffer.read(), overwrite=True)


def main():
    parser = argparse.ArgumentParser(description="Descarga comentarios de YouTube sobre turismo en Tenerife.")
    parser.add_argument("--dry-run", action="store_true", help="Si se especifica, no sube nada a Azure Blob Storage.")
    args = parser.parse_args()

    if not YOUTUBE_API_KEY:
        print("Falta YOUTUBE_API_KEY en el .env. Revisa .env.example.")
        sys.exit(1)

    blob_service_client = get_blob_client()

    all_videos = []
    all_comments = []

    for term in SEARCH_TERMS:
        print(f"Buscando: {term!r}...")
        videos = search_videos(term)
        view_counts = fetch_view_counts([v["video_id"] for v in videos])
        
        for v in videos:
            v["view_count"] = view_counts.get(v["video_id"], 0)
            all_videos.append(v)
            
            comments = fetch_comments(v["video_id"])
            all_comments.extend(comments)

    print(f"Descargados {len(all_videos)} vídeos y {len(all_comments)} comentarios.")
    
    df_videos = pd.DataFrame(all_videos)
    df_comments = pd.DataFrame(all_comments)
    
    # Convertir fechas a string o datetime para Parquet
    if not df_videos.empty:
        df_videos['published_at'] = pd.to_datetime(df_videos['published_at'])
    if not df_comments.empty:
        df_comments['published_at'] = pd.to_datetime(df_comments['published_at'])

    if args.dry_run:
        print("\n--- MODO DRY RUN ACTIVO ---")
        print("No se subirá nada a Azure.")
        print(f"Muestra de vídeos:\n{df_videos.head(3)}")
        print(f"Muestra de comentarios:\n{df_comments.head(3)}")
    else:
        print("Subiendo a Azure...")
        upload_to_azure(blob_service_client, df_videos, "youtube/youtube_videos.parquet", unique_key="video_id")
        upload_to_azure(blob_service_client, df_comments, "youtube/youtube_comments.parquet", unique_key="comment_id")
        print("¡Subida a Azure Blob Storage completada con éxito!")


if __name__ == "__main__":
    main()
