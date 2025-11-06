-- Migration: Add Case Management Tables
-- Date: 2025-11-06
-- Purpose: Add tables for case management and package export

-- Cases table - stores case information
CREATE TABLE IF NOT EXISTS cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'archived', 'closed')),
    created_by VARCHAR(255),
    document_count INTEGER DEFAULT 0
);

-- Case documents junction table - links documents to cases
CREATE TABLE IF NOT EXISTS case_documents (
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL DEFAULT 0,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT,
    PRIMARY KEY (case_id, document_id)
);

-- Packages table - stores export packages
CREATE TABLE IF NOT EXISTS packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    format VARCHAR(20) NOT NULL CHECK (format IN ('zip', 'pdf')),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
    file_path TEXT,
    file_size INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    download_count INTEGER DEFAULT 0
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_case_documents_case_id ON case_documents(case_id);
CREATE INDEX IF NOT EXISTS idx_case_documents_document_id ON case_documents(document_id);
CREATE INDEX IF NOT EXISTS idx_case_documents_order ON case_documents(case_id, display_order);
CREATE INDEX IF NOT EXISTS idx_packages_case_id ON packages(case_id);
CREATE INDEX IF NOT EXISTS idx_packages_status ON packages(status);

-- Create trigger to update case document count
CREATE OR REPLACE FUNCTION update_case_document_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE cases 
        SET document_count = document_count + 1,
            updated_at = NOW()
        WHERE id = NEW.case_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE cases 
        SET document_count = document_count - 1,
            updated_at = NOW()
        WHERE id = OLD.case_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_case_document_count
AFTER INSERT OR DELETE ON case_documents
FOR EACH ROW EXECUTE FUNCTION update_case_document_count();

-- Create trigger to update case updated_at timestamp
CREATE OR REPLACE FUNCTION update_case_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_case_timestamp
BEFORE UPDATE ON cases
FOR EACH ROW EXECUTE FUNCTION update_case_timestamp();

-- Add comments for documentation
COMMENT ON TABLE cases IS 'Stores case information for grouping related documents';
COMMENT ON TABLE case_documents IS 'Junction table linking documents to cases with ordering';
COMMENT ON TABLE packages IS 'Stores export packages (ZIP/PDF) for cases';
COMMENT ON COLUMN cases.document_count IS 'Automatically updated count of documents in this case';
COMMENT ON COLUMN case_documents.display_order IS 'Order of documents within the case for export';
COMMENT ON COLUMN packages.status IS 'Package generation status: pending, processing, ready, or failed';
