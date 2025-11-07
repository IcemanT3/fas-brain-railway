"""
Delta Token Store - Persist OneDrive delta tokens for incremental sync
"""

import os
from typing import Optional
from supabase import create_client, Client

class DeltaTokenStore:
    """Store and retrieve OneDrive delta tokens for incremental sync"""
    
    def __init__(self):
        """Initialize Supabase client for token persistence"""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None
        
        # Fallback to environment variables if database not available
        self.use_env_fallback = not self.supabase
    
    def get_token(self, scope: str) -> Optional[str]:
        """
        Get delta token for a specific scope (e.g., 'inbox', 'by_case', etc.)
        
        Args:
            scope: Token scope identifier (e.g., 'inbox', 'by_case')
        
        Returns:
            Delta token string or None
        """
        if self.use_env_fallback:
            # Fallback to environment variable
            env_key = f"DELTA_TOKEN_{scope.upper()}"
            return os.getenv(env_key)
        
        try:
            # Query database for token
            result = self.supabase.table("sync_state").select("delta_token").eq("scope", scope).limit(1).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0].get("delta_token")
        except Exception as e:
            print(f"Error retrieving delta token for {scope}: {e}")
        
        return None
    
    def set_token(self, scope: str, delta_token: str) -> bool:
        """
        Store delta token for a specific scope
        
        Args:
            scope: Token scope identifier
            delta_token: Delta token to store
        
        Returns:
            True if successful, False otherwise
        """
        if self.use_env_fallback:
            # Cannot persist to environment variables at runtime
            print(f"⚠️  Cannot persist delta token for {scope} - database not available")
            print(f"   Set DELTA_TOKEN_{scope.upper()}={delta_token} in environment")
            return False
        
        try:
            # Upsert token in database
            data = {
                "scope": scope,
                "delta_token": delta_token,
                "updated_at": "now()"
            }
            
            # Check if exists
            existing = self.supabase.table("sync_state").select("id").eq("scope", scope).limit(1).execute()
            
            if existing.data and len(existing.data) > 0:
                # Update existing
                self.supabase.table("sync_state").update(data).eq("scope", scope).execute()
            else:
                # Insert new
                self.supabase.table("sync_state").insert(data).execute()
            
            return True
        except Exception as e:
            print(f"Error storing delta token for {scope}: {e}")
            return False
    
    def get_folder_id(self, scope: str) -> Optional[str]:
        """
        Get cached folder ID for a specific scope
        
        Args:
            scope: Scope identifier (e.g., 'inbox', 'fas_brain_root')
        
        Returns:
            Folder ID or None
        """
        if self.use_env_fallback:
            # Fallback to environment variable
            env_key = f"{scope.upper()}_FOLDER_ID"
            return os.getenv(env_key)
        
        try:
            result = self.supabase.table("sync_state").select("folder_id").eq("scope", scope).limit(1).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0].get("folder_id")
        except Exception as e:
            print(f"Error retrieving folder ID for {scope}: {e}")
        
        return None
    
    def set_folder_id(self, scope: str, folder_id: str) -> bool:
        """
        Store cached folder ID for a specific scope
        
        Args:
            scope: Scope identifier
            folder_id: OneDrive folder ID to cache
        
        Returns:
            True if successful, False otherwise
        """
        if self.use_env_fallback:
            print(f"⚠️  Cannot persist folder ID for {scope} - database not available")
            print(f"   Set {scope.upper()}_FOLDER_ID={folder_id} in environment")
            return False
        
        try:
            # Upsert folder ID in database
            data = {
                "scope": scope,
                "folder_id": folder_id,
                "updated_at": "now()"
            }
            
            # Check if exists
            existing = self.supabase.table("sync_state").select("id").eq("scope", scope).limit(1).execute()
            
            if existing.data and len(existing.data) > 0:
                # Update existing
                self.supabase.table("sync_state").update(data).eq("scope", scope).execute()
            else:
                # Insert new
                self.supabase.table("sync_state").insert(data).execute()
            
            return True
        except Exception as e:
            print(f"Error storing folder ID for {scope}: {e}")
            return False

# Global instance
delta_token_store = DeltaTokenStore()
