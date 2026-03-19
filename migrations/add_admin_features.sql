-- Step 1: Add superadmin to role enum
ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'superadmin';

-- Step 2: Update constraint
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;

-- Step 2.5: Ensure companies table has metadata column
ALTER TABLE companies ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Step 3: Contracts table
CREATE TABLE IF NOT EXISTS contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    uploaded_by UUID REFERENCES users(id),
    name VARCHAR(500) NOT NULL,
    contract_type VARCHAR(100),
    parties JSONB DEFAULT '[]',
    start_date DATE,
    end_date DATE,
    file_path TEXT,
    file_type VARCHAR(50),
    extracted_text TEXT,
    status VARCHAR(50) DEFAULT 'active',
    review_result JSONB,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_contracts_company ON contracts(company_id);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_contracts_end_date ON contracts(end_date);

-- Step 4: Platform logs table
CREATE TABLE IF NOT EXISTS platform_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id),
    user_id UUID REFERENCES users(id),
    endpoint VARCHAR(200),
    method VARCHAR(10),
    status_code INT,
    response_time_ms INT,
    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    ip_address VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_platform_logs_created ON platform_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_platform_logs_company ON platform_logs(company_id);

-- Step 5: Announcements table
CREATE TABLE IF NOT EXISTS announcements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500),
    content TEXT,
    author_id UUID REFERENCES users(id),
    target VARCHAR(50) DEFAULT 'all',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Step 6: Make bi@hrvn.vn a superadmin
UPDATE users SET role = 'superadmin' WHERE email = 'bi@hrvn.vn';
