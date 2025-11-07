"""
Charter-Compliant API Contract Shim

This module adds charter-compliant endpoints to the existing FastAPI app.
Import this after main.py initializes to add contract routes.

Usage in main.py:
    from add_contract_routes import add_contract_compliance
    add_contract_compliance(app, job_queue, async_processor)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class OneDriveSyncRequest(BaseModel):
    """Request to sync a OneDrive folder"""
    folder_path: Optional[str] = None
    recursive: bool = True
    deduplicate: bool = True


def add_contract_compliance(app: FastAPI, job_queue, async_processor):
    """
    Add charter-compliant API contract endpoints to existing FastAPI app.
    
    This adds:
    - POST /sources/onedrive/sync (contract route)
    - GET /admin/jobs/{job_id} (contract route)
    
    Existing routes remain as beta/internal:
    - POST /api/documents/upload (beta)
    - GET /api/jobs/{job_id} (beta)
    """
    
    # ========================================================================
    # CONTRACT-COMPLIANT ROUTES (Charter API)
    # ========================================================================
    
    @app.post("/sources/onedrive/sync")
    async def onedrive_sync_contract(request: OneDriveSyncRequest):
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
            
            logger.info(f"[CONTRACT] OneDrive sync job enqueued: {job_id}")
            
            return {
                "status": "accepted",
                "job_id": job_id,
                "message": "OneDrive sync job queued. Check /admin/jobs/{job_id} for status."
            }
            
        except Exception as e:
            logger.error(f"[CONTRACT] Failed to enqueue OneDrive sync: {e}")
            raise HTTPException(500, f"Failed to enqueue sync job: {str(e)}")
    
    
    @app.get("/admin/jobs/{job_id}")
    async def get_job_status_contract(job_id: str):
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
        
        job = job_queue.get_status(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        
        return {
            "job_id": job.id,
            "type": job.type,
            "status": job.status,
            "progress": job.progress,
            "progress_message": job.progress_message,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "result": job.result,
            "error": job.error
        }
    
    logger.info("✅ Charter-compliant API contract routes added")
    logger.info("   - POST /sources/onedrive/sync")
    logger.info("   - GET /admin/jobs/{job_id}")
    logger.info("   Beta routes: /api/documents/upload, /api/jobs/{job_id}")
