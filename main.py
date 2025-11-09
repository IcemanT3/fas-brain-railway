#!/usr/bin/env python3
"""
FAS Brain - FastAPI Backend
Main application file for Railway deployment
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import sys
from pathlib import Path

# === Preflight: Check Required Environment Variables ===
need = ["SUPABASE_URL","SUPABASE_SERVICE_ROLE_KEY","OPENAI_API_KEY","CHARTER_PROJECT","CHARTER_HASH"]
miss = [k for k in need if not os.getenv(k)]
if miss:
    print(f"❌ Missing environment variables: {', '.join(miss)}")
    sys.exit(1)
print("✅ All required environment variables present")

# === Charter Verification ===
# Verify charter before any other imports or initialization
try:
    from charter_verify import verify_charter
except ImportError:
    print("❌ Charter verification module not found (charter_verify.py missing).")
    sys.exit(1)

# === Step 1: Verify Charter Before Boot ===
try:
    charter_info = verify_charter()
    print(f"✅ Charter OK • {charter_info['project']} • hash={charter_info['hash']} • Phase: {charter_info.get('phase')}")
except Exception as e:
    print(f"❌ Charter verification failed: {e}")
    sys.exit(1)

# Import our existing modules
sys.path.insert(0, str(Path(__file__).parent))

from document_processor import DocumentProcessor
from search_engine import SearchEngine
from entity_manager import EntityManager
from hybrid_search import hybrid_search
from deduplicator import deduplicator
from admin_console import admin_console
from job_queue import job_queue, JobStatus
from async_document_processor import AsyncDocumentProcessor
from case_routes import router as case_router

# Initialize FastAPI
app = FastAPI(
    title="FAS Brain API",
    description="Legal Document Research System with AI-powered search and entity extraction",
    version="1.0.0"
)

# CORS middleware - allow frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
processor = DocumentProcessor()
search_engine = SearchEngine()
entity_manager = EntityManager()
async_processor = AsyncDocumentProcessor()

# Register job handlers and start workers
job_queue.register_handler('process_document', async_processor.process_document)
job_queue.start_workers(num_workers=3)

# Add contract routes
from add_contract_routes import add_contract_compliance
add_contract_compliance(app, job_queue, async_processor)

# Add case management routes
app.include_router(case_router)


# Pydantic models for request/response
class SearchRequest(BaseModel):
    query: str
    entity_filter: Optional[str] = None
    entity_type_filter: Optional[str] = None
    document_type_filter: Optional[str] = None
    top_k: int = 10
    generate_answer: bool = True


class SearchResponse(BaseModel):
    results: List[dict]
    answer: Optional[str] = None
    total_results: int


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    document_type: str
    status: str
    entities: List[dict]


# Health check endpoint
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "FAS Brain API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check with charter verification"""
    return {
        "status": "healthy",
        "database": "connected",
        "charter": {
            "project": charter_info["project"],
            "hash": charter_info["hash"],
            "phase": charter_info.get("phase", "Phase1"),
            "enforced": True
        },
        "services": {
            "processor": "ready",
            "search": "ready",
            "entities": "ready"
        }
    }


# Document endpoints
@app.post("/api/documents/upload")
async def upload_document_async(
    file: UploadFile = File(...)
):
    """
    Async document upload - returns immediately with job_id.
    Client should poll /api/jobs/{job_id} for status.
    
    Implements charter-defined ingestion workflow:
    1. Save file temporarily
    2. Enqueue background job
    3. Return job_id immediately
    """
    try:
        # Save uploaded file to temp directory
        import uuid
        temp_id = str(uuid.uuid4())
        temp_dir = "/tmp/uploads"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = f"{temp_dir}/{temp_id}_{file.filename}"
        
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        # Enqueue processing job
        job_params = {
            'file_path': temp_path,
            'filename': file.filename,
            'file_size': len(content),
            'mime_type': file.content_type or 'application/octet-stream'
        }
        
        try:
            job_id = job_queue.enqueue('process_document', job_params)
        except Exception as e:
            # Queue full - return 429
            os.remove(temp_path)
            raise HTTPException(
                status_code=429,
                detail="Job queue is full - please try again later"
            )
            
        return {
            'job_id': job_id,
            'filename': file.filename,
            'status': 'queued',
            'message': 'Document queued for processing. Check /api/jobs/{job_id} for status.'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents")
async def list_documents(
    document_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List all documents with optional filtering"""
    try:
        documents = processor.list_documents(
            document_type=document_type,
            limit=limit,
            offset=offset
        )
        return {
            "documents": documents,
            "total": len(documents),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents/{document_id}")
async def get_document(document_id: str):
    """Get document details including entities"""
    try:
        document = processor.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return document
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all its chunks"""
    try:
        success = processor.delete_document(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"status": "deleted", "document_id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Job status endpoints
@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get status of a background job.
    
    Returns:
        - status: QUEUED | RUNNING | DONE | ERROR
        - progress: 0.0 to 1.0
        - progress_message: Current step description
        - result: Final result if DONE
        - error: Error message if ERROR
    """
    job = job_queue.get_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return {
        'job_id': job.id,
        'type': job.type,
        'status': job.status,
        'progress': job.progress,
        'progress_message': job.progress_message,
        'created_at': job.created_at.isoformat(),
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'result': job.result,
        'error': job.error
    }


@app.get("/api/jobs")
async def get_queue_stats():
    """
    Get job queue statistics.
    Useful for monitoring and backpressure visibility.
    """
    return {
        'queue_depth': job_queue.get_queue_depth(),
        'running_count': job_queue.get_running_count(),
        'max_queue_size': job_queue.max_queue_size,
        'max_concurrent': job_queue.max_concurrent
    }


# Search endpoints
@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Enhanced hybrid search with entity filtering
    
    - Vector similarity search (semantic)
    - Keyword matching (exact terms)
    - Entity filtering
    - Document type filtering
    - AI answer generation
    """
    try:
        results = search_engine.search(
            query=request.query,
            entity_filter=request.entity_filter,
            entity_type_filter=request.entity_type_filter,
            document_type_filter=request.document_type_filter,
            top_k=request.top_k
        )
        
        answer = None
        if request.generate_answer and results:
            answer = search_engine.generate_answer(request.query, results)
        
        return SearchResponse(
            results=results,
            answer=answer,
            total_results=len(results)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Entity endpoints
@app.get("/api/entities")
async def list_entities(
    entity_type: Optional[str] = None,
    document_id: Optional[str] = None
):
    """List all entities with optional filtering"""
    try:
        entities = entity_manager.list_entities(
            entity_type=entity_type,
            document_id=document_id
        )
        return {
            "entities": entities,
            "total": len(entities)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/entities/stats")
async def entity_statistics():
    """Get entity statistics by type"""
    try:
        stats = entity_manager.get_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/entities/types")
async def entity_types():
    """Get list of all entity types"""
    return {
        "types": [
            "person",
            "organization",
            "location",
            "date",
            "amount",
            "event"
        ]
    }


@app.get("/api/document-types")
async def document_types():
    """Get list of all document types"""
    return {
        "types": [
            "contract",
            "legal_document",
            "evidence",
            "correspondence",
            "recording",
            "ai_opinion"
        ]
    }


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found"}
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Hybrid Search Endpoints

@app.post("/api/search/hybrid")
async def hybrid_search_endpoint(request: SearchRequest):
    """Perform hybrid search combining vector and full-text search"""
    if hybrid_search is None:
        raise HTTPException(status_code=503, detail="Hybrid search service not available")
    try:
        results = await hybrid_search.search(
            query=request.query,
            top_k=request.top_k if hasattr(request, 'top_k') else 10,
            entity_filter=request.entity_filter,
            entity_type_filter=request.entity_type_filter,
            document_type_filter=request.document_type_filter
        )
        return {"success": True, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Deduplication Endpoints

@app.get("/api/admin/duplicates")
async def get_duplicates():
    """Get all duplicate document groups"""
    if deduplicator is None:
        raise HTTPException(status_code=503, detail="Deduplication service not available")
    try:
        groups = await deduplicator.get_duplicate_groups()
        return {"success": True, "duplicate_groups": groups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/deduplication/stats")
async def get_deduplication_stats():
    """Get deduplication statistics"""
    if deduplicator is None:
        raise HTTPException(status_code=503, detail="Deduplication service not available")
    try:
        stats = await deduplicator.get_deduplication_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/duplicates/merge")
async def merge_duplicates(keep_id: str, remove_ids: List[str]):
    """Merge duplicate documents"""
    if deduplicator is None:
        raise HTTPException(status_code=503, detail="Deduplication service not available")
    try:
        result = await deduplicator.merge_duplicates(keep_id, remove_ids)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Admin Console Endpoints

@app.get("/api/admin/environment")
async def validate_environment():
    """Validate environment configuration"""
    if admin_console is None:
        raise HTTPException(status_code=503, detail="Admin console service not available")
    try:
        validation = await admin_console.validate_environment()
        return validation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/metrics")
async def get_system_metrics():
    """Get system resource metrics"""
    if admin_console is None:
        raise HTTPException(status_code=503, detail="Admin console service not available")
    try:
        metrics = await admin_console.get_system_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/ingestion")
async def get_ingestion_stats(hours: int = 24):
    """Get document ingestion statistics"""
    if admin_console is None:
        raise HTTPException(status_code=503, detail="Admin console service not available")
    try:
        stats = await admin_console.get_ingestion_stats(hours)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/queue")
async def get_queue_status():
    """Get processing queue status"""
    if admin_console is None:
        raise HTTPException(status_code=503, detail="Admin console service not available")
    try:
        status = await admin_console.get_processing_queue_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/dashboard")
async def get_health_dashboard():
    """Get comprehensive health dashboard"""
    if admin_console is None:
        raise HTTPException(status_code=503, detail="Admin console service not available")
    try:
        dashboard = await admin_console.get_health_dashboard()
        return dashboard
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


# OneDrive Integration
from onedrive_manager import OneDriveManager
from document_organizer import DocumentOrganizer
from case_package_generator import CasePackageGenerator

onedrive = OneDriveManager()
organizer = DocumentOrganizer()
package_generator = CasePackageGenerator(processor.supabase)


@app.get("/api/onedrive/auth-url")
async def get_onedrive_auth_url():
    """Get OneDrive OAuth authorization URL"""
    try:
        auth_url = onedrive.get_auth_url()
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/callback")
async def onedrive_callback(code: str):
    """Handle OneDrive OAuth callback"""
    try:
        success = onedrive.exchange_code_for_token(code)
        if success:
            # Create folder structure
            onedrive.create_folder_structure()
            return {"status": "success", "message": "OneDrive connected successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to exchange code for token")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/onedrive/process-inbox")
async def process_inbox():
    """
    Process all documents in the OneDrive inbox
    - Analyze each document
    - Organize into appropriate folders
    - Update Supabase database
    - Generate case packages
    """
    try:
        # Get files from inbox
        inbox_files = onedrive.monitor_inbox()
        
        results = []
        for file_info in inbox_files:
            filename = file_info["name"]
            
            # Download file
            temp_path = f"/tmp/{filename}"
            onedrive.download_file(f"00_INBOX/{filename}", temp_path)
            
            # Extract text
            full_text = processor.extractor.extract(temp_path)
            
            # Organize document
            org_result = organizer.organize_document(filename, full_text, onedrive)
            
            # Process in Supabase (with organization metadata)
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
            }).eq("id", proc_result["document_id"]).execute()
            
            results.append({
                "filename": filename,
                "document_id": proc_result["document_id"],
                "organization": org_result,
                "success": org_result["success"]
            })
            
            # Clean up
            os.remove(temp_path)
        
        # Generate updated case packages
        packages = package_generator.generate_all_case_packages()
        for case_name, package_content in packages.items():
            package_generator.save_package_to_onedrive(case_name, package_content, onedrive)
        
        return {
            "processed": len(results),
            "results": results,
            "case_packages_updated": len(packages)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/onedrive/folders")
async def list_onedrive_folders(folder_path: str = ""):
    """List files in a OneDrive folder"""
    try:
        files = onedrive.list_files(folder_path)
        return {"files": files, "folder": folder_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/onedrive/share")
async def create_share_link(folder_path: str, link_type: str = "view"):
    """Create a sharing link for a OneDrive folder"""
    try:
        share_link = onedrive.create_share_link(folder_path, link_type)
        if share_link:
            return {"share_link": share_link, "folder": folder_path}
        else:
            raise HTTPException(status_code=400, detail="Failed to create share link")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/case-packages")
async def list_case_packages():
    """List all available case packages"""
    try:
        cases = [
            "arbitration_employment",
            "derivative_lawsuit",
            "direct_lawsuit",
            "class_action",
            "regulatory_complaints"
        ]
        
        packages = []
        for case in cases:
            docs = package_generator.get_documents_for_case(case)
            packages.append({
                "case_name": case,
                "display_name": case.replace('_', ' ').title(),
                "document_count": len(docs),
                "onedrive_path": f"05_CASE_PACKAGES/{case}_package.md"
            })
        
        return {"packages": packages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/case-packages/generate")
async def generate_case_package(case_name: str):
    """Generate a specific case package"""
    try:
        package_content = package_generator.generate_case_package(case_name)
        onedrive_path = package_generator.save_package_to_onedrive(case_name, package_content, onedrive)
        
        return {
            "case_name": case_name,
            "onedrive_path": onedrive_path,
            "content_preview": package_content[:500] + "..."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Import case manager
from case_manager import case_manager


# Pydantic models for case management
class CaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    created_by: Optional[str] = None


class CaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class CaseDocumentAdd(BaseModel):
    document_id: str
    display_order: Optional[int] = None
    notes: Optional[str] = None


class CaseDocumentReorder(BaseModel):
    document_order: List[str]


class PackageCreate(BaseModel):
    format: str = "zip"  # zip or pdf


# Case Management Endpoints

@app.post("/api/cases")
async def create_case(case_data: CaseCreate):
    """Create a new case"""
    if case_manager is None:
        raise HTTPException(status_code=503, detail="Case management service not available")
    try:
        case = await case_manager.create_case(
            name=case_data.name,
            description=case_data.description,
            created_by=case_data.created_by
        )
        return {"success": True, "case": case}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cases")
async def list_cases(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """List all cases"""
    try:
        cases = await case_manager.list_cases(
            status=status,
            limit=limit,
            offset=offset
        )
        return {"success": True, "cases": cases, "total": len(cases)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    """Get case details with documents"""
    try:
        case = await case_manager.get_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return {"success": True, "case": case}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/cases/{case_id}")
async def update_case(case_id: str, case_data: CaseUpdate):
    """Update case information"""
    try:
        case = await case_manager.update_case(
            case_id=case_id,
            name=case_data.name,
            description=case_data.description,
            status=case_data.status
        )
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return {"success": True, "case": case}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cases/{case_id}")
async def delete_case(case_id: str):
    """Delete a case"""
    try:
        success = await case_manager.delete_case(case_id)
        if not success:
            raise HTTPException(status_code=404, detail="Case not found")
        return {"success": True, "message": "Case deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cases/{case_id}/documents")
async def add_document_to_case(case_id: str, doc_data: CaseDocumentAdd):
    """Add a document to a case"""
    try:
        result = await case_manager.add_document_to_case(
            case_id=case_id,
            document_id=doc_data.document_id,
            display_order=doc_data.display_order,
            notes=doc_data.notes
        )
        return {"success": True, "case_document": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cases/{case_id}/documents/{document_id}")
async def remove_document_from_case(case_id: str, document_id: str):
    """Remove a document from a case"""
    try:
        success = await case_manager.remove_document_from_case(case_id, document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found in case")
        return {"success": True, "message": "Document removed from case"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/cases/{case_id}/documents/reorder")
async def reorder_case_documents(case_id: str, reorder_data: CaseDocumentReorder):
    """Reorder documents in a case"""
    try:
        success = await case_manager.reorder_documents(
            case_id=case_id,
            document_order=reorder_data.document_order
        )
        return {"success": True, "message": "Documents reordered successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cases/{case_id}/items")
async def get_case_items(case_id: str):
    """Get list of documents in a case (charter endpoint)"""
    try:
        case = await case_manager.get_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        documents = case.get("documents", [])
        return {"success": True, "items": documents, "total": len(documents)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Package Export Endpoints

@app.post("/api/packages")
async def create_package(package_data: PackageCreate, case_id: str):
    """Create a package export for a case"""
    try:
        package = await case_manager.create_package(
            case_id=case_id,
            format=package_data.format
        )
        return {"success": True, "package": package}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/packages/{package_id}")
async def get_package(package_id: str):
    """Get package status and information"""
    try:
        package = await case_manager.get_package(package_id)
        if not package:
            raise HTTPException(status_code=404, detail="Package not found")
        return {"success": True, "package": package}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/packages/{package_id}/download")
async def download_package(package_id: str):
    """Download a package file"""
    from fastapi.responses import FileResponse
    
    try:
        file_path = await case_manager.get_package_file_path(package_id)
        
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Package file not found or not ready")
        
        # Increment download count
        package = await case_manager.get_package(package_id)
        if package:
            await case_manager.supabase.table("packages").update({
                "download_count": package.get("download_count", 0) + 1
            }).eq("id", package_id).execute()
        
        return FileResponse(
            file_path,
            media_type="application/zip",
            filename=os.path.basename(file_path)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
