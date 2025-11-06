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

# Import our existing modules
sys.path.insert(0, str(Path(__file__).parent))

from document_processor import DocumentProcessor
from search_engine import SearchEngine
from entity_manager import EntityManager

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
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "services": {
            "processor": "ready",
            "search": "ready",
            "entities": "ready"
        }
    }


# Document endpoints
@app.post("/api/documents/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    sub_category: Optional[str] = Form(None)
):
    """
    Upload and process a document
    
    - Extracts text
    - Categorizes document
    - Generates embeddings
    - Extracts entities
    """
    try:
        # Save uploaded file temporarily
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Process document
        result = processor.process(
            temp_path,
            manual_category=document_type,
            manual_sub_category=sub_category
        )
        
        # Clean up temp file
        os.remove(temp_path)
        
        if not result:
            raise HTTPException(status_code=500, detail="Document processing failed")
        
        return DocumentResponse(
            document_id=result['document_id'],
            filename=result['filename'],
            document_type=result['document_type'],
            status="processed",
            entities=result.get('entities', [])
        )
    
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
