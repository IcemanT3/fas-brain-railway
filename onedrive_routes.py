"""
OneDrive Integration Routes
Side-effect free router - all manager initialization happens inside handlers
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal

router = APIRouter(prefix="/api/onedrive", tags=["OneDrive"])

# Lazy imports - only import when needed inside handlers
def get_onedrive_manager():
    """Lazy load OneDriveManager to avoid import-time side effects"""
    try:
        from onedrive_manager import OneDriveManager
        return OneDriveManager()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OneDrive manager initialization failed: {e}")


@router.get("/auth-url")
async def get_auth_url():
    """Get OneDrive OAuth authorization URL - always available"""
    import os
    from urllib.parse import urlencode
    
    client_id = os.getenv("MICROSOFT_CLIENT_ID")
    tenant_id = os.getenv("MICROSOFT_TENANT_ID")
    
    if not client_id or not tenant_id:
        raise HTTPException(status_code=500, detail="OneDrive OAuth not configured (missing MICROSOFT_CLIENT_ID or MICROSOFT_TENANT_ID)")
    
    # Build OAuth URL
    redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI", "https://fas-brain-railway-production.up.railway.app/auth/callback")
    scope = "Files.ReadWrite.All offline_access"
    
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope,
        "response_mode": "query"
    }
    
    auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize?{urlencode(params)}"
    return {"auth_url": auth_url}


@router.get("/callback")
async def oauth_callback(code: str):
    """Handle OneDrive OAuth callback"""
    manager = get_onedrive_manager()
    
    try:
        success = manager.exchange_code_for_token(code)
        if success:
            # Create folder structure
            manager.create_folder_structure()
            return {"status": "success", "message": "OneDrive connected successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to exchange code for token")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/folders")
async def list_folders(folder_path: str = ""):
    """List files in a OneDrive folder"""
    manager = get_onedrive_manager()
    
    # Check if authenticated
    if not manager.access_token:
        raise HTTPException(status_code=401, detail="OneDrive not connected. Use /api/onedrive/auth-url to authorize.")
    
    try:
        files = manager.list_files(folder_path)
        return {"files": files, "folder": folder_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/share")
async def create_share_link(folder_path: str, link_type: str = "view"):
    """Create a sharing link for a OneDrive folder"""
    manager = get_onedrive_manager()
    
    # Check if authenticated
    if not manager.access_token:
        raise HTTPException(status_code=401, detail="OneDrive not connected. Use /api/onedrive/auth-url to authorize.")
    
    try:
        share_link = manager.create_share_link(folder_path, link_type)
        if share_link:
            return {"share_link": share_link, "folder": folder_path}
        else:
            raise HTTPException(status_code=400, detail="Failed to create share link")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-inbox")
async def process_inbox():
    """Process all documents in the OneDrive inbox"""
    manager = get_onedrive_manager()
    
    # Check if authenticated
    if not manager.access_token:
        raise HTTPException(status_code=401, detail="OneDrive not connected. Use /api/onedrive/auth-url to authorize.")
    
    try:
        from document_organizer import DocumentOrganizer
        from document_processor import DocumentProcessor
        
        organizer = DocumentOrganizer()
        processor = DocumentProcessor()
        
        # Get files from inbox
        inbox_files = manager.monitor_inbox()
        
        results = []
        for file_info in inbox_files:
            filename = file_info["name"]
            
            # Download file
            temp_path = f"/tmp/{filename}"
            manager.download_file(f"00_INBOX/{filename}", temp_path)
            
            # Extract text
            full_text = processor.extractor.extract(temp_path)
            
            # Organize document
            org_result = organizer.organize_document(filename, full_text, manager)
            
            # Process in Supabase
            proc_result = processor.process(
                temp_path,
                manual_category=org_result["analysis"].get("document_type")
            )
            
            # Update document with organization metadata
            processor.supabase.table("documents").update({
                "metadata": {
                    **proc_result.get("metadata", {}),
                    "analysis": org_result["analysis"],
                    "organization_paths": org_result["paths"]
                }
            }).eq("id", proc_result["id"]).execute()
            
            results.append({
                "filename": filename,
                "document_id": proc_result["id"],
                "paths": org_result["paths"]
            })
        
        return {
            "status": "success",
            "processed": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
