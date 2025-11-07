"""
Charter-Compliant API Contract Routes

This module implements the official API contract defined in the project charter.
These routes are stable, documented, and guaranteed to remain compatible.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Literal
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Charter Contract"])

# ---- Contract payloads ----
class OneDriveSyncRequest(BaseModel):
    site_id: Optional[str] = Field(None, description="SharePoint site id (optional if default configured)")
    drive_id: Optional[str] = Field(None, description="Drive id (optional if default configured)")
    folder_id: Optional[str] = Field(None, description="Folder id/path to sync")
    mode: Literal["full","delta"] = Field("delta", description="delta = resume with token; full = rescan")
    reason: Optional[str] = Field(None, description="Audit note for who/why triggered")

class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["QUEUED","RUNNING","DONE","ERROR"]
    progress: int
    message: Optional[str] = None

# ---- Internal adapters (will be set by main.py) ----
_job_queue = None
_async_processor = None

def set_services(job_queue, async_processor):
    """Set internal service references"""
    global _job_queue, _async_processor
    _job_queue = job_queue
    _async_processor = async_processor
    logger.info("✅ Contract routes services initialized")

# ---- Helper functions ----
async def enqueue_onedrive_sync(site_id=None, drive_id=None, folder_id=None, mode="delta", reason=None):
    """Enqueue OneDrive sync job and return job_id"""
    if not _job_queue or not _async_processor:
        raise HTTPException(500, "Sync service not initialized")
    
    job_id = _job_queue.enqueue(
        job_type="onedrive_sync",
        handler=_async_processor.sync_onedrive_folder,
        params={
            "site_id": site_id,
            "drive_id": drive_id,
            "folder_id": folder_id,
            "mode": mode,
            "reason": reason
        }
    )
    logger.info(f"[CONTRACT] OneDrive sync enqueued: {job_id} (mode={mode}, reason={reason})")
    return job_id

async def get_job(job_id: str):
    """Get job status from queue"""
    if not _job_queue:
        raise HTTPException(500, "Job service not initialized")
    
    job = _job_queue.get_status(job_id)
    if not job:
        return None
    
    # Convert to contract format
    class JobInfo:
        def __init__(self, job):
            self.id = job.id
            self.status = job.status
            self.progress = int(job.progress * 100)  # Convert 0.0-1.0 to 0-100
            self.message = job.progress_message
    
    return JobInfo(job)

# ---- Charter-compliant endpoints ----

@router.post("/sources/onedrive/sync", status_code=status.HTTP_202_ACCEPTED)
async def onedrive_sync(req: OneDriveSyncRequest):
    """
    **CONTRACT ROUTE** - Trigger manual OneDrive folder ingestion
    
    This endpoint implements the charter API contract for OneDrive integration.
    It enqueues a background job to sync documents from OneDrive/SharePoint.
    
    Request:
        - site_id: SharePoint site (optional if default configured)
        - drive_id: Drive ID (optional if default configured)
        - folder_id: Folder path to sync (null = sync all)
        - mode: "delta" (incremental) or "full" (rescan)
        - reason: Audit note for who/why triggered
    
    Response:
        - status: "accepted"
        - job_id: UUID to track sync progress
        
    Use GET /admin/jobs/{job_id} to check status.
    """
    try:
        job_id = await enqueue_onedrive_sync(
            site_id=req.site_id,
            drive_id=req.drive_id,
            folder_id=req.folder_id,
            mode=req.mode,
            reason=req.reason
        )
        return {"status": "accepted", "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CONTRACT] OneDrive sync failed: {e}")
        raise HTTPException(500, f"Failed to enqueue sync: {str(e)}")

@router.get("/admin/jobs/{job_id}", response_model=JobStatusResponse)
async def job_status(job_id: str):
    """
    **CONTRACT ROUTE** - Standardized job status endpoint
    
    This endpoint implements the charter API contract for job monitoring.
    It returns the current status and progress of any background job.
    
    Response:
        - job_id: Job identifier
        - status: QUEUED | RUNNING | DONE | ERROR
        - progress: 0-100 (percentage complete)
        - message: Human-readable status message
    """
    try:
        j = await get_job(job_id)
        if not j:
            raise HTTPException(404, "Job not found")
        
        return JobStatusResponse(
            job_id=j.id,
            status=j.status,
            progress=j.progress,
            message=j.message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CONTRACT] Job status failed: {e}")
        raise HTTPException(500, f"Failed to get job status: {str(e)}")
