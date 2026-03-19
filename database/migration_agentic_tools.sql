-- ============================================
-- Agentic AI Tools — Full Document Control
-- Database Migration
-- ============================================

-- Document edit history tracking
CREATE TABLE IF NOT EXISTS document_edits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    edit_type VARCHAR(50) NOT NULL, -- 'create', 'edit', 'delete', 'restore', 'move'
    old_content TEXT,
    new_content TEXT,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_document_edits_document ON document_edits(document_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_document_edits_company ON document_edits(company_id, created_at DESC);

-- Folders/Cases for organizing documents and contracts
CREATE TABLE IF NOT EXISTS folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    parent_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    folder_type VARCHAR(50) DEFAULT 'general', -- 'general', 'case', 'project', 'department'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_folders_company ON folders(company_id);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id);

-- Add folder_id to documents if not exists
ALTER TABLE documents ADD COLUMN IF NOT EXISTS folder_id UUID REFERENCES folders(id) ON DELETE SET NULL;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_documents_folder ON documents(folder_id) WHERE folder_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_documents_deleted ON documents(deleted_at) WHERE deleted_at IS NOT NULL;

-- Add folder_id to contracts if not exists
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS folder_id UUID REFERENCES folders(id) ON DELETE SET NULL;
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS content TEXT;  -- For full text content (renamed from extracted_text)

CREATE INDEX IF NOT EXISTS idx_contracts_folder ON contracts(folder_id) WHERE folder_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contracts_deleted ON contracts(deleted_at) WHERE deleted_at IS NOT NULL;

-- Add search index for full-text search in documents and contracts
CREATE INDEX IF NOT EXISTS idx_documents_fulltext ON documents USING GIN (to_tsvector('simple', COALESCE(extracted_text, '')));
CREATE INDEX IF NOT EXISTS idx_contracts_fulltext ON contracts USING GIN (to_tsvector('simple', COALESCE(content, '')));

-- Comment for explanation
COMMENT ON TABLE document_edits IS 'Tracks all edits made to documents for audit trail and version history';
COMMENT ON TABLE folders IS 'Organizational folders for documents and contracts (cases, projects, departments)';
