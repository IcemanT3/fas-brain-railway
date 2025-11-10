"""
OneDrive Manager - Handle OneDrive integration for FAS Brain
"""

import os
import requests
from typing import List, Dict, Optional
import json
from datetime import datetime, timedelta
from oauth_token_store import oauth_token_store

class OneDriveManager:
    """Manage OneDrive folder structure and file operations"""
    
    def __init__(self):
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID")
        self.redirect_uri = os.getenv("OAUTH_REDIRECT_URL", os.getenv("MICROSOFT_REDIRECT_URI", "https://fas-brain-railway-production.up.railway.app/api/onedrive/callback"))
        
        # Service account support (optional, defaults to /me for delegated auth)
        self.user_id = os.getenv("ONEDRIVE_USER_ID")  # e.g., "dih-sync@fascorp.net" or user GUID
        
        # Cached folder IDs for faster access
        self.fas_brain_folder_id = os.getenv("FAS_BRAIN_FOLDER_ID")  # Cache root folder ID
        self.inbox_folder_id = os.getenv("INBOX_FOLDER_ID")  # Cache INBOX folder ID
        
        if not all([self.client_id, self.client_secret, self.tenant_id]):
            print("WARNING: Microsoft credentials not configured. OneDrive features will be disabled.")
        
        # Load tokens from persistent storage
        self._load_tokens()
        
        # If tokens not loaded, initialize as None
        if not hasattr(self, 'access_token'):
            self.access_token = None
            self.refresh_token = None
            self.token_expiry = None
        
        # OneDrive folder structure - all under FAS_Brain/ to avoid root clutter
        self.root_folder = "FAS_Brain"
        self.folder_structure = {
            "00_INBOX": "Hot folder for new documents",
            "01_BY_CASE": {
                "arbitration_employment": "Employment arbitration case",
                "derivative_lawsuit": "Derivative lawsuit",
                "direct_lawsuit": "Direct lawsuit",
                "class_action": "Class action lawsuit",
                "regulatory_complaints": "Regulatory complaints"
            },
            "02_BY_ISSUE": {
                "fraudulent_inducement": "Fraudulent inducement issues",
                "breach_of_contract": "Breach of contract",
                "fiduciary_duty": "Fiduciary duty violations",
                "securities_fraud": "Securities fraud"
            },
            "03_BY_PARTY": {
                "trident": "Trident Capital related",
                "chris_johnson": "Chris Johnson related",
                "board_members": "Board members related"
            },
            "04_PROCESSED_ORIGINALS": "Archive of original processed documents",
            "05_CASE_PACKAGES": "Comprehensive case summaries"
        }
    
    def _load_tokens(self):
        """Load OAuth tokens from persistent storage"""
        token_data = oauth_token_store.get_tokens()
        if token_data:
            self.access_token = token_data.get("access_token")
            self.refresh_token = token_data.get("refresh_token")
            self.token_expiry = token_data.get("token_expiry")
            print(f"✅ Loaded OAuth tokens from storage (expires: {self.token_expiry})")
        else:
            print("ℹ️  No stored OAuth tokens found")
    
    def _save_tokens(self):
        """Save OAuth tokens to persistent storage"""
        if self.access_token:
            expires_in = 3600  # Default 1 hour
            if self.token_expiry:
                expires_in = int((self.token_expiry - datetime.now()).total_seconds())
            oauth_token_store.set_tokens(self.access_token, self.refresh_token, expires_in)
    
    def get_auth_url(self) -> str:
        """Generate OAuth authorization URL"""
        if not all([self.client_id, self.client_secret, self.tenant_id]):
            raise ValueError("Microsoft credentials not configured. Please set MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, and MICROSOFT_TENANT_ID environment variables.")
        auth_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": "Files.ReadWrite.All Sites.ReadWrite.All offline_access",
            "response_mode": "query"
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{auth_url}?{query_string}"
    
    def exchange_code_for_token(self, code: str) -> bool:
        """Exchange authorization code for access token"""
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code"
        }
        
        response = requests.post(token_url, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
            
            # Save tokens to persistent storage
            self._save_tokens()
            
            return True
        
        return False
    
    def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            return False
        
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token"
        }
        
        response = requests.post(token_url, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.refresh_token = token_data.get("refresh_token", self.refresh_token)
            expires_in = token_data.get("expires_in", 3600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
            
            # Save refreshed tokens to persistent storage
            self._save_tokens()
            
            return True
        
        return False
    
    def ensure_token_valid(self):
        """Ensure access token is valid, refresh if needed"""
        if not self.access_token:
            raise Exception("No access token available. Please authenticate first.")
        
        if self.token_expiry and datetime.now() >= self.token_expiry:
            if not self.refresh_access_token():
                raise Exception("Failed to refresh access token")
    
    def _get_drive_path(self) -> str:
        """Get drive path for API calls (supports both /me and service account)"""
        if self.user_id:
            # Service account or specific user
            return f"/users/{self.user_id}/drive"
        else:
            # Delegated auth to current user
            return "/me/drive"
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated request to Microsoft Graph API"""
        self.ensure_token_valid()
        
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        kwargs["headers"] = headers
        
        url = f"https://graph.microsoft.com/v1.0{endpoint}"
        response = requests.request(method, url, **kwargs)
        
        return response
    
    def create_folder(self, parent_path: str, folder_name: str) -> Optional[Dict]:
        """Create a folder in OneDrive"""
        drive_path = self._get_drive_path()
        endpoint = f"{drive_path}/root:/{parent_path}:/children"
        
        data = {
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail"  # Fail if exists (idempotent)
        }
        
        response = self._make_request("POST", endpoint, json=data)
        
        if response.status_code in [200, 201]:
            return response.json()
        
        return None
    
    def create_folder_structure(self) -> Dict:
        """Create the complete FAS Brain folder structure in OneDrive (idempotent)"""
        created = []
        skipped = []
        errors = []
        
        def safe_create(parent_path: str, folder_name: str, full_path: str):
            """Create folder and track result"""
            result = self.create_folder(parent_path, folder_name)
            if result:
                created.append(full_path)
                return True
            else:
                # Check if folder already exists (409 conflict)
                try:
                    # Try to get folder to verify it exists
                    drive_path = self._get_drive_path()
                    endpoint = f"{drive_path}/root:/{full_path}"
                    response = self._make_request("GET", endpoint)
                    if response.status_code == 200:
                        skipped.append(full_path)
                        return True
                except:
                    pass
                errors.append(full_path)
                return False
        
        try:
            # Create root FAS_Brain folder first
            safe_create("", self.root_folder, self.root_folder)
            
            # Create subfolders under FAS_Brain/
            for folder_name, description in self.folder_structure.items():
                if isinstance(description, str):
                    # Simple folder under FAS_Brain/
                    full_path = f"{self.root_folder}/{folder_name}"
                    safe_create(self.root_folder, folder_name, full_path)
                elif isinstance(description, dict):
                    # Folder with subfolders under FAS_Brain/
                    full_path = f"{self.root_folder}/{folder_name}"
                    safe_create(self.root_folder, folder_name, full_path)
                    parent_path = f"{self.root_folder}/{folder_name}"
                    for subfolder_name in description.keys():
                        subfolder_full_path = f"{parent_path}/{subfolder_name}"
                        safe_create(parent_path, subfolder_name, subfolder_full_path)
            
            return {
                "success": len(errors) == 0,
                "created": created,
                "skipped": skipped,
                "errors": errors,
                "total": len(created) + len(skipped) + len(errors)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "created": created,
                "skipped": skipped,
                "errors": errors
            }
    
    def upload_file(self, local_path: str, onedrive_path: str) -> Optional[Dict]:
        """Upload a file to OneDrive"""
        drive_path = self._get_drive_path()
        endpoint = f"{drive_path}/root:/{onedrive_path}:/content"
        
        with open(local_path, 'rb') as f:
            file_content = f.read()
        
        headers = {"Content-Type": "application/octet-stream"}
        response = self._make_request("PUT", endpoint, data=file_content, headers=headers)
        
        if response.status_code in [200, 201]:
            return response.json()
        
        return None
    
    def download_file(self, onedrive_path: str, local_path: str) -> bool:
        """Download a file from OneDrive"""
        drive_path = self._get_drive_path()
        endpoint = f"{drive_path}/root:/{onedrive_path}:/content"
        
        response = self._make_request("GET", endpoint)
        
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            return True
        
        return False
    
    def list_files(self, folder_path: str = "") -> List[Dict]:
        """List files in a OneDrive folder"""
        drive_path = self._get_drive_path()
        if folder_path:
            endpoint = f"{drive_path}/root:/{folder_path}:/children"
        else:
            endpoint = f"{drive_path}/root/children"
        
        response = self._make_request("GET", endpoint)
        
        if response.status_code == 200:
            return response.json().get("value", [])
        
        return []
    
    def delete_file(self, onedrive_path: str) -> bool:
        """Delete a file from OneDrive"""
        drive_path = self._get_drive_path()
        endpoint = f"{drive_path}/root:/{onedrive_path}"
        
        response = self._make_request("DELETE", endpoint)
        
        return response.status_code == 204
    
    def create_share_link(self, onedrive_path: str, link_type: str = "view") -> Optional[str]:
        """Create a sharing link for a file or folder"""
        drive_path = self._get_drive_path()
        endpoint = f"{drive_path}/root:/{onedrive_path}:/createLink"
        
        data = {
            "type": link_type,  # "view" or "edit"
            "scope": "anonymous"  # Anyone with the link can access
        }
        
        response = self._make_request("POST", endpoint, json=data)
        
        if response.status_code in [200, 201]:
            return response.json().get("link", {}).get("webUrl")
        
        return None
    
    def get_file_metadata(self, onedrive_path: str) -> Optional[Dict]:
        """Get metadata for a file"""
        drive_path = self._get_drive_path()
        endpoint = f"{drive_path}/root:/{onedrive_path}"
        
        response = self._make_request("GET", endpoint)
        
        if response.status_code == 200:
            return response.json()
        
        return None
    
    def resolve_folder_id(self, folder_path: str) -> Optional[str]:
        """Resolve folder path to folder ID for delta sync"""
        drive_path = self._get_drive_path()
        endpoint = f"{drive_path}/root:/{folder_path}"
        
        response = self._make_request("GET", endpoint)
        
        if response.status_code == 200:
            return response.json().get("id")
        
        return None
    
    def get_folder_delta(self, folder_id: str, delta_token: Optional[str] = None) -> Dict:
        """
        Get delta changes for a folder using folder ID and delta token.
        
        This is the recommended approach for production sync:
        - Use folder ID instead of path for stability
        - Persist delta_token between syncs for incremental updates
        - Only fetches changes since last sync
        
        Args:
            folder_id: OneDrive folder ID (from resolve_folder_id)
            delta_token: Optional delta token from previous sync
        
        Returns:
            Dict with:
                - items: List of changed items
                - delta_token: New delta token to persist
                - delta_link: Delta link for next sync
        """
        drive_path = self._get_drive_path()
        
        if delta_token:
            # Use delta token for incremental sync
            endpoint = f"{drive_path}/items/{folder_id}/delta"
            params = {"token": delta_token}
        else:
            # Initial sync - get all items
            endpoint = f"{drive_path}/items/{folder_id}/delta"
            params = {}
        
        response = self._make_request("GET", endpoint, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract delta link and token for next sync
            delta_link = data.get("@odata.deltaLink", "")
            new_delta_token = None
            
            if delta_link and "token=" in delta_link:
                # Extract token from delta link
                new_delta_token = delta_link.split("token=")[1].split("&")[0]
            
            return {
                "items": data.get("value", []),
                "delta_token": new_delta_token,
                "delta_link": delta_link
            }
        
        return {
            "items": [],
            "delta_token": None,
            "delta_link": None
        }
    
    def monitor_inbox(self) -> List[Dict]:
        """Monitor the inbox folder for new files"""
        return self.list_files("FAS_Brain/00_INBOX")
    
    def move_file(self, source_path: str, dest_folder_path: str) -> bool:
        """Move a file from one location to another"""
        endpoint = f"/me/drive/root:/{source_path}"
        
        # Get destination folder ID
        dest_folder = self.get_file_metadata(dest_folder_path)
        if not dest_folder:
            return False
        
        data = {
            "parentReference": {
                "id": dest_folder["id"]
            }
        }
        
        response = self._make_request("PATCH", endpoint, json=data)
        
        return response.status_code == 200
