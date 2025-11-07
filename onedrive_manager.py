"""
OneDrive Manager - Handle OneDrive integration for FAS Brain
"""

import os
import requests
from typing import List, Dict, Optional
import json
from datetime import datetime, timedelta

class OneDriveManager:
    """Manage OneDrive folder structure and file operations"""
    
    def __init__(self):
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID")
        self.redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI", "https://fas-brain-railway-production.up.railway.app/auth/callback")
        
        if not all([self.client_id, self.client_secret, self.tenant_id]):
            print("WARNING: Microsoft credentials not configured. OneDrive features will be disabled.")
        
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        
        # OneDrive folder structure
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
            return True
        
        return False
    
    def ensure_token_valid(self):
        """Ensure access token is valid, refresh if needed"""
        if not self.access_token:
            raise Exception("No access token available. Please authenticate first.")
        
        if self.token_expiry and datetime.now() >= self.token_expiry:
            if not self.refresh_access_token():
                raise Exception("Failed to refresh access token")
    
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
        endpoint = f"/me/drive/root:/{parent_path}:/children"
        
        data = {
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename"
        }
        
        response = self._make_request("POST", endpoint, json=data)
        
        if response.status_code in [200, 201]:
            return response.json()
        
        return None
    
    def create_folder_structure(self) -> bool:
        """Create the complete FAS Brain folder structure in OneDrive"""
        try:
            # Create root folders
            for folder_name, description in self.folder_structure.items():
                if isinstance(description, str):
                    # Simple folder
                    self.create_folder("", folder_name)
                elif isinstance(description, dict):
                    # Folder with subfolders
                    self.create_folder("", folder_name)
                    for subfolder_name in description.keys():
                        self.create_folder(folder_name, subfolder_name)
            
            return True
        except Exception as e:
            print(f"Error creating folder structure: {e}")
            return False
    
    def upload_file(self, local_path: str, onedrive_path: str) -> Optional[Dict]:
        """Upload a file to OneDrive"""
        endpoint = f"/me/drive/root:/{onedrive_path}:/content"
        
        with open(local_path, 'rb') as f:
            file_content = f.read()
        
        headers = {"Content-Type": "application/octet-stream"}
        response = self._make_request("PUT", endpoint, data=file_content, headers=headers)
        
        if response.status_code in [200, 201]:
            return response.json()
        
        return None
    
    def download_file(self, onedrive_path: str, local_path: str) -> bool:
        """Download a file from OneDrive"""
        endpoint = f"/me/drive/root:/{onedrive_path}:/content"
        
        response = self._make_request("GET", endpoint)
        
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            return True
        
        return False
    
    def list_files(self, folder_path: str = "") -> List[Dict]:
        """List files in a OneDrive folder"""
        if folder_path:
            endpoint = f"/me/drive/root:/{folder_path}:/children"
        else:
            endpoint = "/me/drive/root/children"
        
        response = self._make_request("GET", endpoint)
        
        if response.status_code == 200:
            return response.json().get("value", [])
        
        return []
    
    def delete_file(self, onedrive_path: str) -> bool:
        """Delete a file from OneDrive"""
        endpoint = f"/me/drive/root:/{onedrive_path}"
        
        response = self._make_request("DELETE", endpoint)
        
        return response.status_code == 204
    
    def create_share_link(self, onedrive_path: str, link_type: str = "view") -> Optional[str]:
        """Create a sharing link for a file or folder"""
        endpoint = f"/me/drive/root:/{onedrive_path}:/createLink"
        
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
        endpoint = f"/me/drive/root:/{onedrive_path}"
        
        response = self._make_request("GET", endpoint)
        
        if response.status_code == 200:
            return response.json()
        
        return None
    
    def monitor_inbox(self) -> List[Dict]:
        """Monitor the inbox folder for new files"""
        return self.list_files("00_INBOX")
    
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
