"""
OAuth Token Store - Persist OneDrive OAuth tokens
"""

import os
from typing import Optional, Dict
from supabase import create_client, Client
from datetime import datetime, timedelta
import json

class OAuthTokenStore:
    """Store and retrieve OneDrive OAuth tokens"""
    
    def __init__(self):
        """Initialize Supabase client for token persistence"""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None
        
        # Fallback to environment variables if database not available
        self.use_env_fallback = not self.supabase
    
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
            # Query database for tokens
            result = self.supabase.table("oauth_tokens").select("*").eq("service", "onedrive").limit(1).execute()
            
            if result.data and len(result.data) > 0:
                token_data = result.data[0]
                return {
                    "access_token": token_data.get("access_token"),
                    "refresh_token": token_data.get("refresh_token"),
                    "token_expiry": datetime.fromisoformat(token_data.get("token_expiry")) if token_data.get("token_expiry") else None
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
            # Upsert tokens in database
            data = {
                "service": "onedrive",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expiry": token_expiry.isoformat(),
                "updated_at": "now()"
            }
            
            # Check if exists
            existing = self.supabase.table("oauth_tokens").select("id").eq("service", "onedrive").limit(1).execute()
            
            if existing.data and len(existing.data) > 0:
                # Update existing
                self.supabase.table("oauth_tokens").update(data).eq("service", "onedrive").execute()
            else:
                # Insert new
                self.supabase.table("oauth_tokens").insert(data).execute()
            
            print(f"✅ OAuth tokens stored successfully (expires: {token_expiry.isoformat()})")
            return True
        except Exception as e:
            print(f"❌ Error storing OAuth tokens: {e}")
            return False

# Global instance
oauth_token_store = OAuthTokenStore()
