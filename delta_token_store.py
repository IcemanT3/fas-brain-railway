"""
Delta Token Store - Persist OneDrive delta tokens for incremental sync
"""

import os
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

class DeltaTokenStore:
    """Store and retrieve OneDrive delta tokens for incremental sync"""
    
    def __init__(self):
        """Initialize PostgreSQL connection for token persistence"""
        self.db_url = os.getenv("SUPABASE_DB_URL")
        
        # Fallback to environment variables if database not available
        self.use_env_fallback = not self.db_url
        
        # Ensure table exists on init
        if not self.use_env_fallback:
            self._ensure_table_exists()
    
    def _get_connection(self):
        """Get a new database connection"""
        return psycopg2.connect(self.db_url)
    
    def _ensure_table_exists(self):
        """Ensure the sync_state table exists"""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sync_state (
                    id BIGSERIAL PRIMARY KEY,
                    scope TEXT NOT NULL UNIQUE,
                    delta_token TEXT,
                    folder_id TEXT,
                    last_sync TIMESTAMP WITH TIME ZONE,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            conn.commit()
            cur.close()
            conn.close()
            print("✅ sync_state table ensured")
        except Exception as e:
            print(f"Error ensuring sync_state table: {e}")
    
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
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT delta_token FROM sync_state WHERE scope = %s LIMIT 1", (scope,))
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if result:
                return result['delta_token']
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
            conn = self._get_connection()
            cur = conn.cursor()
            
            # Upsert using ON CONFLICT
            cur.execute("""
                INSERT INTO sync_state (scope, delta_token, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (scope)
                DO UPDATE SET delta_token = EXCLUDED.delta_token, updated_at = NOW()
            """, (scope, delta_token))
            
            conn.commit()
            cur.close()
            conn.close()
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
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT folder_id FROM sync_state WHERE scope = %s LIMIT 1", (scope,))
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if result:
                return result['folder_id']
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
            conn = self._get_connection()
            cur = conn.cursor()
            
            # Upsert using ON CONFLICT
            cur.execute("""
                INSERT INTO sync_state (scope, folder_id, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (scope)
                DO UPDATE SET folder_id = EXCLUDED.folder_id, updated_at = NOW()
            """, (scope, folder_id))
            
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Error storing folder ID for {scope}: {e}")
            return False

# Global instance
delta_token_store = DeltaTokenStore()
