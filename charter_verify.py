"""
charter_verify.py — Charter Verification Module
Verifies project charter integrity before application startup
"""

import os
import sys
from supabase import create_client, Client

def verify_charter():
    """
    Verify charter integrity against Supabase project_charter table.
    
    Returns:
        dict: Charter information including project, hash, and phase
        
    Raises:
        Exception: If charter verification fails
    """
    # Get environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    expected_project = os.getenv("CHARTER_PROJECT", "DIH")
    expected_hash = os.getenv("CHARTER_HASH")
    
    # Validate environment variables
    if not supabase_url:
        raise Exception("SUPABASE_URL environment variable not set")
    if not supabase_key:
        raise Exception("SUPABASE_SERVICE_ROLE_KEY environment variable not set")
    if not expected_hash:
        raise Exception("CHARTER_HASH environment variable not set")
    
    try:
        # Connect to Supabase
        supabase: Client = create_client(supabase_url, supabase_key)
        
        # Query project_charter table
        response = supabase.table("project_charter").select("*").eq("project", expected_project).execute()
        
        if not response.data or len(response.data) == 0:
            raise Exception(f"Charter not found for project '{expected_project}'")
        
        charter = response.data[0]
        actual_hash = charter.get("last_revision_hash")
        
        # Verify hash matches
        if actual_hash != expected_hash:
            raise Exception(
                f"Charter hash mismatch!\n"
                f"Expected: {expected_hash}\n"
                f"Actual:   {actual_hash}\n"
                f"Charter has been modified without updating environment variables."
            )
        
        # Return charter info
        return {
            "project": charter.get("project"),
            "hash": actual_hash,
            "phase": charter.get("phase", "Phase1"),
            "content": charter.get("content"),
            "created_at": charter.get("created_at"),
            "updated_at": charter.get("updated_at")
        }
        
    except Exception as e:
        # Re-raise with context
        raise Exception(f"Charter verification failed: {str(e)}")


def read_charter():
    """
    Read the full charter content from Supabase.
    
    Returns:
        dict: Complete charter information
    """
    return verify_charter()


if __name__ == "__main__":
    # Test charter verification
    try:
        info = verify_charter()
        print(f"✅ Charter OK")
        print(f"   Project: {info['project']}")
        print(f"   Hash: {info['hash']}")
        print(f"   Phase: {info.get('phase')}")
        print(f"   Content length: {len(info.get('content', ''))} characters")
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)
