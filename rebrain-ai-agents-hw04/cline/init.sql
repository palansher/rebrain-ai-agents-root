CREATE TABLE IF NOT EXISTS news (
    id             BIGSERIAL PRIMARY KEY,
    source         TEXT NOT NULL,
    title          TEXT NOT NULL,
    link           TEXT NOT NULL UNIQUE,
    published_at   TIMESTAMPTZ NOT NULL,
    text           TEXT NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_news_source ON news(source);
CREATE INDEX IF NOT EXISTS idx_news_published_at ON news(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_link ON news(link);

CREATE TABLE IF NOT EXISTS entities (
    id        BIGSERIAL PRIMARY KEY,
    news_id   BIGINT NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    text      TEXT NOT NULL,
    label     TEXT NOT NULL,
    count     INT NOT NULL DEFAULT 1,
    UNIQUE (news_id, text, label)
);

CREATE INDEX IF NOT EXISTS idx_entities_news_id ON entities(news_id);
CREATE INDEX IF NOT EXISTS idx_entities_label ON entities(label);