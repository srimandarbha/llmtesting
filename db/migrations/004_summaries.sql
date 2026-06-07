CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS historical_shift_summaries (
    id UUID PRIMARY KEY,
    shift_name VARCHAR NOT NULL,
    summary_text TEXT NOT NULL,
    embedding vector(384),
    is_auto_generated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shift_summary_embedding 
ON historical_shift_summaries 
USING hnsw (embedding vector_l2_ops) 
WITH (m = 16, ef_construction = 64);
