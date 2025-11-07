"""
Charter-Compliant API Contract Routes

These routes implement the API contract defined in the project charter.
They forward requests to the underlying async job queue system.

Contract routes (charter-compliant):
- POST /sources/onedrive/sync - Trigger OneDrive folder sync
- GET /admin/jobs/{job_id} - Check job status

Beta routes (for testing, not in contract):
- POST /api/documents/upload - Direct document upload
- GET /api/jobs/{job_id} - Job status (beta path)
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Contract-compliant router
contract_router = APIRouter(tags=["Contract API"])

# Beta router
beta_router = APIRouter(tags=["Beta API"])


class OneDriveSyncRequest(BaseModel):
    """Request to sync a OneDrive folder"""
    folder_path: Optional[str] = None  # If None, sync all configured folders
    recursive: bool = True
    deduplicate: bool = True


class JobStatusResponse(BaseModel):
    """Standard job status response"""
    job_id: str
    type: str
    status: str  # QUEUED, RUNNING, DONE, ERROR
    progress: float  # 0.0 to 1.0
    progress_message: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# Global reference to job queue (will be set by main.py)
job_queue = None
async_processor = None


def set_dependencies(queue, processor):
    """Set job queue and processor references"""
    global job_queue, async_processor
    job_queue = queue
    async_processor = processor


# ============================================================================
# CONTRACT-COMPLIANT ROUTES (Charter API)
# ============================================================================

@contract_router.post("/sources/onedrive/sync")
async def onedrive_sync(request: OneDriveSyncRequest):
    """
    **CONTRACT ROUTE** - Trigger OneDrive folder synchronization
    
    This endpoint implements the charter API contract for OneDrive integration.
    It enqueues a background job to sync documents from OneDrive.
    
    Returns:
        - status: "accepted"
        - job_id: UUID to track sync progress
        
    Use GET /admin/jobs/{job_id} to check status.
    """
    if not job_queue or not async_processor:
        raise HTTPException(500, "Job queue not initialized")
    
    try:
        # Enqueue OneDrive sync job
        job_id = job_queue.enqueue(
            job_type="onedrive_sync",
            handler=async_processor.sync_onedrive_folder,
            params={
                "folder_path": request.folder_path,
                "recursive": request.recursive,
                "deduplicate": request.deduplicate
            }
        )
        
        logger.info(f"OneDrive sync job enqueued: {job_id}")
        
        return {
            "status": "accepted",
            "job_id": job_id,
            "message": "OneDrive sync job queued. Check /admin/jobs/{job_id} for status."
        }
        
    except Exception as e:
        logger.error(f"Failed to enqueue OneDrive sync: {e}")
        raise HTTPException(500, f"Failed to enqueue sync job: {str(e)}")


@contract_router.get("/admin/jobs/{job_id}")
async def get_job_status_admin(job_id: str) -> JobStatusResponse:
    """
    **CONTRACT ROUTE** - Get job status (admin namespace)
    
    This endpoint implements the charter API contract for job monitoring.
    It returns the current status and progress of any background job.
    
    Returns:
        - job_id: Job identifier
        - type: Job type (process_document, onedrive_sync, etc.)
        - status: QUEUED | RUNNING | DONE | ERROR
        - progress: 0.0 to 1.0
        - progress_message: Human-readable status
        - result: Job result (when DONE)
        - error: Error message (when ERROR)
    """
    if not job_queue:
        raise HTTPException(500, "Job queue not initialized")
    
    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    
    return JobStatusResponse(
        job_id=job.job_id,
        type=job.job_type,
        status=job.status,
        progress=job.progress,
        progress_message=job.progress_message,
        result=job.result,
        error=job.error
    )


# ============================================================================
# BETA ROUTES (Testing/Development - Not in Charter Contract)
# ============================================================================

@beta_router.post("/api/documents/upload")
async def upload_document_beta(file: UploadFile = File(...)):
    """
    **BETA ROUTE** - Direct document upload (async)
    
    This is a beta endpoint for testing async document processing.
    For production, use the charter-compliant OneDrive sync workflow.
    
    Returns immediately with job_id. Document is processed in background.
    """
    if not job_queue or not async_processor:
        raise HTTPException(500, "Job queue not initialized")
    
    # Check queue capacity
    stats = job_queue.get_stats()
    if stats["queue_depth"] >= stats["max_queue_size"]:
        raise HTTPException(429, "Queue full. Try again later.")
    
    try:
        # Save uploaded file
        import os
        import uuid
        upload_dir = "/tmp/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_id = str(uuid.uuid4())
        file_path = os.path.join(upload_dir, f"{file_id}_{file.filename}")
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Enqueue processing job
        job_id = job_queue.enqueue(
            job_type="process_document",
            handler=async_processor.process_document,
            params={"file_path": file_path, "filename": file.filename}
        )
        
        logger.info(f"Document upload queued: {file.filename} -> {job_id}")
        
        return {
            "job_id": job_id,
            "filename": file.filename,
            "status": "queued",
            "message": "Document queued for processing. Check /api/jobs/{job_id} for status."
        }
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(500, f"Upload failed: {str(e)}")


@beta_router.get("/api/jobs/{job_id}")
async def get_job_status_beta(job_id: str):
    """
    **BETA ROUTE** - Get job status (beta namespace)
    
    Same as /admin/jobs/{job_id} but in beta namespace.
    Use the admin endpoint for production.
    """
    if not job_queue:
        raise HTTPException(500, "Job queue not initialized")
    
    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    
    return {
        "job_id": job.job_id,
        "type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "progress_message": job.progress_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "result": job.result,
        "error": job.error
    }


@beta_router.get("/api/jobs")
async def get_queue_stats_beta():
    """
    **BETA ROUTE** - Get queue statistics
    
    Returns current queue depth, running jobs, and capacity limits.
    """
    if not job_queue:
        raise HTTPException(500, "Job queue not initialized")
    
    return job_queue.get_stats()
