-- Storage for the documentation index.
--
-- The source page's URL changes whenever the page is updated, so a document
-- is identified by a fixed slug, never by its URL. The URL is recorded per
-- chunk so answers can cite exactly what was indexed.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    slug            text PRIMARY KEY,           -- e.g. 'libra-user-guide'
    entry_url       text NOT NULL,              -- stable page that links to the current version
    current_url     text,                       -- resolved URL of the version last indexed
    content_sha256  text,                       -- hash of that version; unchanged hash = skip
    embedding_model text,                       -- model that produced the stored vectors
    indexed_at      timestamptz
);

-- The vector dimension must match the embedding model (decided in the ingestion PR).
CREATE TABLE chunks (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_slug    text NOT NULL REFERENCES documents (slug) ON DELETE CASCADE,
    source_url  text NOT NULL,
    heading     text,                           -- section path, e.g. 'Jobs > GPU partitions'
    ordinal     integer NOT NULL,               -- position within the document
    body        text NOT NULL,
    embedding   vector(1024) NOT NULL,
    body_tsv    tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED,
    UNIQUE (doc_slug, ordinal)
);

CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_body_fts ON chunks USING gin (body_tsv);
