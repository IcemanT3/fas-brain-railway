"""
Case Management API Routes
Provides endpoints for case creation, document organization, and ZIP export
"""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from typing import Optional, List
from case_manager import case_manager

router = APIRouter(prefix="/api/cases", tags=["Cases"])


class CreateCaseRequest(BaseModel):
    name: str
    description: Optional[str] = None


class UpdateCaseRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class AddDocumentRequest(BaseModel):
    document_id: str
    notes: Optional[str] = None


class ReorderDocumentsRequest(BaseModel):
    document_order: List[str]


@router.post("")
async def create_case(request: CreateCaseRequest):
    """Create a new case"""
    try:
        if not case_manager:
            raise HTTPException(status_code=503, detail="Case management service not available")
        
        case = await case_manager.create_case(
            name=request.name,
            description=request.description
        )
        return {"success": True, "case": case}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_cases(status: Optional[str] = None, limit: int = 100, offset: int = 0):
    """List all cases"""
    try:
        if not case_manager:
            raise HTTPException(status_code=503, detail="Case management service not available")
        
        cases = await case_manager.list_cases(status=status, limit=limit, offset=offset)
        return {"success": True, "cases": cases, "total": len(cases)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{case_id}")
async def get_case(case_id: str):
    """Get case details with documents"""
    try:
        if not case_manager:
            raise HTTPException(status_code=503, detail="Case management service not available")
        
        case = await case_manager.get_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        return {"success": True, "case": case}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{case_id}")
async def update_case(case_id: str, request: UpdateCaseRequest):
    """Update case details"""
    try:
        if not case_manager:
            raise HTTPException(status_code=503, detail="Case management service not available")
        
        case = await case_manager.update_case(
            case_id=case_id,
            name=request.name,
            description=request.description,
            status=request.status
        )
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        return {"success": True, "case": case}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{case_id}")
async def delete_case(case_id: str):
    """Delete a case"""
    try:
        if not case_manager:
            raise HTTPException(status_code=503, detail="Case management service not available")
        
        success = await case_manager.delete_case(case_id)
        if not success:
            raise HTTPException(status_code=404, detail="Case not found")
        
        return {"success": True, "message": "Case deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{case_id}/documents")
async def add_document_to_case(case_id: str, request: AddDocumentRequest):
    """Add a document to a case"""
    try:
        if not case_manager:
            raise HTTPException(status_code=503, detail="Case management service not available")
        
        case_doc = await case_manager.add_document_to_case(
            case_id=case_id,
            document_id=request.document_id,
            notes=request.notes
        )
        return {"success": True, "case_document": case_doc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{case_id}/documents/{document_id}")
async def remove_document_from_case(case_id: str, document_id: str):
    """Remove a document from a case"""
    try:
        if not case_manager:
            raise HTTPException(status_code=503, detail="Case management service not available")
        
        success = await case_manager.remove_document_from_case(case_id, document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not in case")
        
        return {"success": True, "message": "Document removed from case"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{case_id}/reorder")
async def reorder_documents(case_id: str, request: ReorderDocumentsRequest):
    """Reorder documents in a case"""
    try:
        if not case_manager:
            raise HTTPException(status_code=503, detail="Case management service not available")
        
        success = await case_manager.reorder_documents(case_id, request.document_order)
        return {"success": True, "message": "Documents reordered"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{case_id}/export")
async def export_case(case_id: str):
    """Export case as ZIP file"""
    try:
        if not case_manager:
            raise HTTPException(status_code=503, detail="Case management service not available")
        
        # Create package
        package = await case_manager.create_package(case_id, format="zip")
        
        if not package:
            raise HTTPException(status_code=404, detail="Case not found")
        
        # Wait for package to be ready (in production, this would be async with polling)
        # For now, return package info
        return {
            "success": True,
            "package": package,
            "message": "Package generation started. Poll /api/packages/{package_id} for status"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{case_id}/export/download")
async def download_case_export(case_id: str):
    """Download case ZIP file directly (synchronous)"""
    try:
        if not case_manager:
            raise HTTPException(status_code=503, detail="Case management service not available")
        
        # Get case
        case = await case_manager.get_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        # Generate ZIP synchronously
        zip_path = await case_manager._generate_zip(case)
        
        # Read ZIP file
        with open(zip_path, 'rb') as f:
            zip_data = f.read()
        
        # Clean up temp file
        import os
        os.remove(zip_path)
        
        # Return ZIP file
        case_name_safe = "".join(c for c in case["name"] if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{case_name_safe}.zip"
        
        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
