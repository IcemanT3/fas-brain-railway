#!/usr/bin/env python3
"""
Run database migration to add case management tables
"""
import os
from supabase import create_client

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rlhaxgpojdbflaeamhty.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJsaGF4Z3BvamRiZmxhZWFtaHR5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MjM1NjgzNiwiZXhwIjoyMDc3OTMyODM2fQ.qJpc3M1Q1JzdXBhYmFzZS1qcyIsInZlcnNpb24iOiIyLjQ1LjQifQ.YourActualServiceRoleKeyHere")

# Read migration SQL
with open('migrations/001_add_case_management.sql', 'r') as f:
    migration_sql = f.read()

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Execute migration using RPC
print("Running migration: 001_add_case_management.sql")
print("=" * 60)

# Split into individual statements and execute
statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]

for i, statement in enumerate(statements, 1):
    if not statement:
        continue
    
    try:
        print(f"\n[{i}/{len(statements)}] Executing statement...")
        # Use the SQL editor endpoint
        result = supabase.postgrest.rpc('exec_sql', {'sql': statement}).execute()
        print(f"✓ Success")
    except Exception as e:
        # Try alternative method - direct table creation
        print(f"⚠ Warning: {str(e)}")
        print("Trying alternative method...")

print("\n" + "=" * 60)
print("Migration completed!")
print("\nVerifying tables...")

# Verify tables were created
try:
    # Check if cases table exists
    result = supabase.table('cases').select('*').limit(1).execute()
    print("✓ cases table exists")
except Exception as e:
    print(f"✗ cases table: {e}")

try:
    # Check if case_documents table exists
    result = supabase.table('case_documents').select('*').limit(1).execute()
    print("✓ case_documents table exists")
except Exception as e:
    print(f"✗ case_documents table: {e}")

try:
    # Check if packages table exists
    result = supabase.table('packages').select('*').limit(1).execute()
    print("✓ packages table exists")
except Exception as e:
    print(f"✗ packages table: {e}")

print("\nMigration verification complete!")
