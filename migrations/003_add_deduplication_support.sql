-- Add deduplication support to documents table

-- Add columns for duplicate tracking
ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT FALSE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS original_document_id UUID REFERENCES documents(id) ON DELETE SET NULL;

-- Add index on file_hash for fast duplicate detection
CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);

-- Add index on is_duplicate for filtering
CREATE INDEX IF NOT EXISTS idx_documents_is_duplicate ON documents(is_duplicate) WHERE is_duplicate = TRUE;

-- Create function to find duplicate documents
CREATE OR REPLACE FUNCTION find_duplicate_documents()
RETURNS TABLE (
  file_hash TEXT,
  duplicate_count BIGINT,
  document_ids UUID[],
  total_size BIGINT
)
LANGUAGE SQL
AS $$
  SELECT
    d.file_hash,
    COUNT(*) as duplicate_count,
    ARRAY_AGG(d.id) as document_ids,
    SUM(d.file_size) as total_size
  FROM documents d
  WHERE d.file_hash IS NOT NULL
  GROUP BY d.file_hash
  HAVING COUNT(*) > 1
  ORDER BY duplicate_count DESC, total_size DESC;
$$;

-- Create function to get deduplication savings
CREATE OR REPLACE FUNCTION get_deduplication_savings()
RETURNS TABLE (
  total_documents BIGINT,
  unique_documents BIGINT,
  duplicate_documents BIGINT,
  total_size BIGINT,
  unique_size BIGINT,
  wasted_size BIGINT,
  savings_percentage NUMERIC
)
LANGUAGE SQL
AS $$
  WITH stats AS (
    SELECT
      COUNT(*) as total_docs,
      COUNT(DISTINCT file_hash) as unique_docs,
      SUM(file_size) as total_bytes
    FROM documents
    WHERE file_hash IS NOT NULL
  ),
  unique_sizes AS (
    SELECT
      file_hash,
      MAX(file_size) as size
    FROM documents
    WHERE file_hash IS NOT NULL
    GROUP BY file_hash
  )
  SELECT
    s.total_docs as total_documents,
    s.unique_docs as unique_documents,
    s.total_docs - s.unique_docs as duplicate_documents,
    s.total_bytes as total_size,
    COALESCE(SUM(u.size), 0) as unique_size,
    s.total_bytes - COALESCE(SUM(u.size), 0) as wasted_size,
    CASE
      WHEN s.total_bytes > 0 THEN
        ROUND(((s.total_bytes - COALESCE(SUM(u.size), 0))::NUMERIC / s.total_bytes::NUMERIC) * 100, 2)
      ELSE 0
    END as savings_percentage
  FROM stats s
  CROSS JOIN unique_sizes u
  GROUP BY s.total_docs, s.unique_docs, s.total_bytes;
$$;

-- Add comments
COMMENT ON COLUMN documents.is_duplicate IS 'Flag indicating if this document is a duplicate of another';
COMMENT ON COLUMN documents.original_document_id IS 'Reference to the original document if this is a duplicate';
COMMENT ON FUNCTION find_duplicate_documents IS 'Finds all groups of duplicate documents based on file hash';
COMMENT ON FUNCTION get_deduplication_savings IS 'Calculates storage savings from deduplication';
