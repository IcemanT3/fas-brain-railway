-- Create oauth_tokens table for storing OneDrive OAuth tokens
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id BIGSERIAL PRIMARY KEY,
    service TEXT NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expiry TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on service for faster lookups
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_service ON oauth_tokens(service);

-- Add comment
COMMENT ON TABLE oauth_tokens IS 'Stores OAuth access and refresh tokens for external services';
