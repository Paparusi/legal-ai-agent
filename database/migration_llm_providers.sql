-- Database migration for Multi-LLM Provider System
-- Created: 2026-03-19

-- Add LLM config to companies metadata (metadata column should already be JSONB)
-- Example stored config:
-- {
--   "llm_provider": {
--     "provider": "openai",
--     "auth_method": "api_key",
--     "api_key": "encrypted_xxx",
--     "encrypted": true,
--     "model": "gpt-4o"
--   }
-- }

-- Ensure metadata column exists in companies table
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'companies' AND column_name = 'metadata'
    ) THEN
        ALTER TABLE companies ADD COLUMN metadata JSONB DEFAULT '{}';
    END IF;
END $$;

-- OAuth state tokens (temporary, for OAuth flow)
CREATE TABLE IF NOT EXISTS oauth_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    provider VARCHAR(50) NOT NULL,
    state_token VARCHAR(255) NOT NULL UNIQUE,
    redirect_uri TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '10 minutes'
);

-- Index for fast lookup by state token
CREATE INDEX IF NOT EXISTS idx_oauth_states_token ON oauth_states(state_token);

-- Index for cleanup job (delete expired tokens)
CREATE INDEX IF NOT EXISTS idx_oauth_states_expires ON oauth_states(expires_at);

-- Cleanup function for expired tokens (run daily)
CREATE OR REPLACE FUNCTION cleanup_expired_oauth_states()
RETURNS void AS $$
BEGIN
    DELETE FROM oauth_states WHERE expires_at < NOW() - INTERVAL '1 hour';
END;
$$ LANGUAGE plpgsql;

-- Optional: Create scheduled job to cleanup (requires pg_cron extension)
-- SELECT cron.schedule('cleanup-oauth', '0 */6 * * *', 'SELECT cleanup_expired_oauth_states()');

COMMENT ON TABLE oauth_states IS 'Temporary OAuth state tokens for LLM provider connections';
COMMENT ON COLUMN companies.metadata IS 'JSON metadata including llm_provider config';
