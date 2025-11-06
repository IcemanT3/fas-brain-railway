#!/usr/bin/env python3
"""
Create case management tables in Supabase
Run this once to set up the database schema
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client

# Supabase credentials
SUPABASE_URL = "https://rlhaxgpojdbflaeamhty.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJsaGF4Z3BvamRiZmxhZWFtaHR5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MjM1NjgzNiwiZXhwIjoyMDc3OTMyODM2fQ.qJpc3M1Q1JzdXBhYmFzZS1qcyIsInZlcnNpb24iOiIyLjQ1LjQifQ.YourActualServiceRoleKeyHere"

print("Initializing Supabase client...")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("\nCreating case management tables...")
print("=" * 60)

# Note: Supabase Python client doesn't support DDL operations directly
# We'll document what needs to be created manually in Supabase SQL Editor

sql_to_run = """
-- Run this SQL in Supabase SQL Editor (https://supabase.com/dashboard/project/rlhaxgpojdbflaeamhty/sql)

-- 1. Cases table
CREATE TABLE IF NOT EXISTS cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'active',
    created_by VARCHAR(255),
    document_count INTEGER DEFAULT 0
);

-- 2. Case documents junction table
CREATE TABLE IF NOT EXISTS case_documents (
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL DEFAULT 0,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT,
    PRIMARY KEY (case_id, document_id)
);

-- 3. Packages table
CREATE TABLE IF NOT EXISTS packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    format VARCHAR(20) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    file_path TEXT,
    file_size INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    download_count INTEGER DEFAULT 0
);

-- 4. Create indexes
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_case_documents_case_id ON case_documents(case_id);
CREATE INDEX IF NOT EXISTS idx_packages_case_id ON packages(case_id);
"""

print(sql_to_run)
print("=" * 60)
print("\n✓ SQL script ready")
print("\nTo create tables:")
print("1. Go to: https://supabase.com/dashboard/project/rlhaxgpojdbflaeamhty/sql")
print("2. Copy and paste the SQL above")
print("3. Click 'Run'")
print("\nOR I can try to create them programmatically...")

# Try to verify if tables already exist
print("\nChecking if tables exist...")
try:
    result = supabase.table('cases').select('count').limit(1).execute()
    print("✓ cases table already exists!")
except Exception as e:
    print(f"✗ cases table does not exist yet: {str(e)[:100]}")

try:
    result = supabase.table('case_documents').select('count').limit(1).execute()
    print("✓ case_documents table already exists!")
except Exception as e:
    print(f"✗ case_documents table does not exist yet: {str(e)[:100]}")

try:
    result = supabase.table('packages').select('count').limit(1).execute()
    print("✓ packages table already exists!")
except Exception as e:
    print(f"✗ packages table does not exist yet: {str(e)[:100]}")

print("\nDone!")
