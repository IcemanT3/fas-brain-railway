"""
Charter-Compliant API Contract Integration

This module integrates the charter-compliant contract routes into the main FastAPI app.

Usage in main.py:
    from add_contract_routes import add_contract_compliance
    add_contract_compliance(app, job_queue, async_processor)
"""

from contract_routes import router as contract_router, set_services
import logging

logger = logging.getLogger(__name__)


def add_contract_compliance(app, job_queue, async_processor):
    """
    Add charter-compliant API contract routes to FastAPI app.
    
    This adds:
    - POST /sources/onedrive/sync (contract route)
    - GET /admin/jobs/{job_id} (contract route)
    
    Existing routes remain as beta/internal:
    - POST /api/documents/upload (beta)
    - GET /api/jobs/{job_id} (beta)
    """
    
    # Register OneDrive sync handler
    job_queue.register_handler('onedrive_sync', async_processor.sync_onedrive_folder)
    logger.info("✅ Registered onedrive_sync handler")
    
    # Set service dependencies for contract routes
    set_services(job_queue, async_processor)
    
    # Include contract router
    app.include_router(contract_router)
    
    logger.info("✅ Charter-compliant API contract routes added")
    logger.info("   - POST /sources/onedrive/sync")
    logger.info("   - GET /admin/jobs/{job_id}")
    logger.info("   Beta routes: /api/documents/upload, /api/jobs/{job_id}")
