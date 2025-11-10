"""
OAuth Token Store - Persist OneDrive OAuth tokens
"""

import os
from typing import Optional, Dict
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

class OAuthTokenStore:
    """Store and retrieve OneDrive OAuth tokens"""
    
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
        """Ensure the oauth_tokens table exists"""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    id BIGSERIAL PRIMARY KEY,
                    service TEXT NOT NULL UNIQUE,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    token_expiry TIMESTAMP WITH TIME ZONE,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            conn.commit()
            cur.close()
            conn.close()
            print("✅ oauth_tokens table ensured")
        except Exception as e:
            print(f"Error ensuring oauth_tokens table: {e}")
    
    def get_tokens(self) -> Optional[Dict]:
        """
        Get OAuth tokens (access_token, refresh_token, expiry)
        
        Returns:
            Dict with access_token, refresh_token, token_expiry or None
        """
        if self.use_env_fallback:
            # Fallback to environment variables
            access_token = os.getenv("ONEDRIVE_ACCESS_TOKEN")
            refresh_token = os.getenv("ONEDRIVE_REFRESH_TOKEN")
            expiry_str = os.getenv("ONEDRIVE_TOKEN_EXPIRY")
            
            if access_token:
                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_expiry": datetime.fromisoformat(expiry_str) if expiry_str else None
                }
            return None
        
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                "SELECT access_token, refresh_token, token_expiry FROM oauth_tokens WHERE service = %s LIMIT 1",
                ('onedrive',)
            )
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if result:
                return {
                    "access_token": result['access_token'],
                    "refresh_token": result['refresh_token'],
                    "token_expiry": result['token_expiry']
                }
        except Exception as e:
            print(f"Error retrieving OAuth tokens: {e}")
        
        return None
    
    def set_tokens(self, access_token: str, refresh_token: Optional[str] = None, expires_in: int = 3600) -> bool:
        """
        Store OAuth tokens
        
        Args:
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            expires_in: Token expiry time in seconds
        
        Returns:
            True if successful, False otherwise
        """
        token_expiry = datetime.now() + timedelta(seconds=expires_in)
        
        if self.use_env_fallback:
            # Cannot persist to environment variables at runtime
            print(f"⚠️  Cannot persist OAuth tokens - database not available")
            print(f"   Set ONEDRIVE_ACCESS_TOKEN={access_token}")
            print(f"   Set ONEDRIVE_REFRESH_TOKEN={refresh_token}")
            print(f"   Set ONEDRIVE_TOKEN_EXPIRY={token_expiry.isoformat()}")
            return False
        
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            # Upsert using ON CONFLICT
            cur.execute("""
                INSERT INTO oauth_tokens (service, access_token, refresh_token, token_expiry, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (service)
                DO UPDATE SET 
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_expiry = EXCLUDED.token_expiry,
                    updated_at = NOW()
            """, ('onedrive', access_token, refresh_token, token_expiry))
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"✅ OAuth tokens stored successfully (expires: {token_expiry.isoformat()})")
            return True
        except Exception as e:
            print(f"❌ Error storing OAuth tokens: {e}")
            return False

# Global instance
oauth_token_store = OAuthTokenStore()
