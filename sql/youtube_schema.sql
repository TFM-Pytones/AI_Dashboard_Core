-- Issue #13 — Integración API de YouTube
-- Tablas crudas para vídeos y comentarios relacionados con turismo en Tenerife.

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.youtube_videos (
    video_id        TEXT PRIMARY KEY,
    search_term     TEXT NOT NULL,
    title           TEXT,
    channel_title   TEXT,
    published_at    TIMESTAMPTZ,
    view_count      BIGINT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.youtube_comments (
    comment_id      TEXT PRIMARY KEY,
    video_id        TEXT NOT NULL REFERENCES bronze.youtube_videos(video_id),
    author          TEXT,
    text            TEXT,
    like_count      INTEGER,
    published_at    TIMESTAMPTZ,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_youtube_comments_video_id ON bronze.youtube_comments(video_id);
