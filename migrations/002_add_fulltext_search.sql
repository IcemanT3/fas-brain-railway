-- Add full-text search support to chunks table

-- Add tsvector column for full-text search
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS content_tsvector tsvector;

-- Create function to update tsvector
CREATE OR REPLACE FUNCTION chunks_content_tsvector_update() RETURNS trigger AS $$
BEGIN
  NEW.content_tsvector := to_tsvector('english', COALESCE(NEW.content, ''));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update tsvector
DROP TRIGGER IF EXISTS chunks_content_tsvector_trigger ON chunks;
CREATE TRIGGER chunks_content_tsvector_trigger
  BEFORE INSERT OR UPDATE OF content
  ON chunks
  FOR EACH ROW
  EXECUTE FUNCTION chunks_content_tsvector_update();

-- Update existing rows
UPDATE chunks SET content_tsvector = to_tsvector('english', COALESCE(content, ''));

-- Create GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS idx_chunks_content_tsvector ON chunks USING GIN(content_tsvector);

-- Create function for hybrid search (combines vector + full-text)
CREATE OR REPLACE FUNCTION hybrid_search(
  query_embedding vector(384),
  query_text text,
  match_count int DEFAULT 10,
  vector_weight float DEFAULT 0.6,
  fulltext_weight float DEFAULT 0.4
)
RETURNS TABLE (
  id uuid,
  document_id uuid,
  content text,
  chunk_index int,
  vector_score float,
  fulltext_score float,
  combined_score float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  WITH vector_results AS (
    SELECT
      c.id,
      c.document_id,
      c.content,
      c.chunk_index,
      1 - (c.embedding <=> query_embedding) AS similarity
    FROM chunks c
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count * 2
  ),
  fulltext_results AS (
    SELECT
      c.id,
      c.document_id,
      c.content,
      c.chunk_index,
      ts_rank(c.content_tsvector, plainto_tsquery('english', query_text)) AS rank
    FROM chunks c
    WHERE c.content_tsvector @@ plainto_tsquery('english', query_text)
    ORDER BY rank DESC
    LIMIT match_count * 2
  ),
  combined AS (
    SELECT
      COALESCE(v.id, f.id) AS id,
      COALESCE(v.document_id, f.document_id) AS document_id,
      COALESCE(v.content, f.content) AS content,
      COALESCE(v.chunk_index, f.chunk_index) AS chunk_index,
      COALESCE(v.similarity, 0) AS vector_score,
      COALESCE(f.rank, 0) AS fulltext_score
    FROM vector_results v
    FULL OUTER JOIN fulltext_results f ON v.id = f.id
  )
  SELECT
    c.id,
    c.document_id,
    c.content,
    c.chunk_index,
    c.vector_score,
    c.fulltext_score,
    (c.vector_score * vector_weight + c.fulltext_score * fulltext_weight) AS combined_score
  FROM combined c
  ORDER BY combined_score DESC
  LIMIT match_count;
END;
$$;

-- Add comment
COMMENT ON FUNCTION hybrid_search IS 'Performs hybrid search combining vector similarity and full-text search with configurable weights';
