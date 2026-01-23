-- Create rules table in PostgreSQL
-- Run this script if the table doesn't exist: psql -U bess_agent -d bess_agent -f scripts/create_rules_table.sql

-- Create rules table
CREATE TABLE IF NOT EXISTS rules (
    rule_id VARCHAR(100) NOT NULL,
    site_id VARCHAR(100) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    device_types JSONB,
    device_ids JSONB,
    condition JSONB NOT NULL,
    severity VARCHAR(50),
    priority INTEGER DEFAULT 0,
    actions JSONB,
    metadata JSONB,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    PRIMARY KEY (rule_id, site_id),
    FOREIGN KEY (site_id) REFERENCES sites(site_id) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_rules_site_id ON rules(site_id);
CREATE INDEX IF NOT EXISTS idx_rules_enabled ON rules(enabled);
CREATE INDEX IF NOT EXISTS idx_rules_priority ON rules(priority DESC);
CREATE INDEX IF NOT EXISTS idx_rules_device_types ON rules USING GIN(device_types);

-- Verify table creation
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'rules'
ORDER BY ordinal_position;

