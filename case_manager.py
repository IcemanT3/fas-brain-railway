"""
Case Management Module
Handles creation, retrieval, and management of legal cases
"""
import os
import uuid
import zipfile
import io
from datetime import datetime
from typing import List, Dict, Optional
from supabase import create_client, Client

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rlhaxgpojdbflaeamhty.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Only create client if key is available
if SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None


class CaseManager:
    """Manages legal cases and document grouping"""
    
    def __init__(self):
        if supabase is None:
            raise RuntimeError("Supabase client not initialized. SUPABASE_SERVICE_ROLE_KEY environment variable is required.")
        self.supabase = supabase
    
    async def create_case(
        self,
        name: str,
        description: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Dict:
        """
        Create a new case
        
        Args:
            name: Case name
            description: Optional case description
            created_by: Optional creator identifier
            
        Returns:
            Created case data
        """
        case_data = {
            "name": name,
            "description": description,
            "created_by": created_by,
            "status": "active",
            "document_count": 0
        }
        
        result = self.supabase.table("cases").insert(case_data).execute()
        return result.data[0] if result.data else None
    
    async def get_case(self, case_id: str) -> Optional[Dict]:
        """
        Get case by ID
        
        Args:
            case_id: Case UUID
            
        Returns:
            Case data with documents
        """
        # Get case info
        case_result = self.supabase.table("cases").select("*").eq("id", case_id).execute()
        
        if not case_result.data:
            return None
        
        case = case_result.data[0]
        
        # Get case documents
        docs_result = self.supabase.table("case_documents").select(
            "document_id, display_order, added_at, notes, documents(*)"
        ).eq("case_id", case_id).order("display_order").execute()
        
        case["documents"] = docs_result.data if docs_result.data else []
        
        return case
    
    async def list_cases(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        List all cases
        
        Args:
            status: Filter by status (active, archived, closed)
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of cases
        """
        query = self.supabase.table("cases").select("*")
        
        if status:
            query = query.eq("status", status)
        
        query = query.order("created_at", desc=True).limit(limit).offset(offset)
        
        result = query.execute()
        return result.data if result.data else []
    
    async def update_case(
        self,
        case_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Update case information
        
        Args:
            case_id: Case UUID
            name: New case name
            description: New description
            status: New status
            
        Returns:
            Updated case data
        """
        update_data = {}
        
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if status is not None:
            update_data["status"] = status
        
        if not update_data:
            return await self.get_case(case_id)
        
        result = self.supabase.table("cases").update(update_data).eq("id", case_id).execute()
        return result.data[0] if result.data else None
    
    async def delete_case(self, case_id: str) -> bool:
        """
        Delete a case
        
        Args:
            case_id: Case UUID
            
        Returns:
            True if deleted successfully
        """
        result = self.supabase.table("cases").delete().eq("id", case_id).execute()
        return len(result.data) > 0 if result.data else False
    
    async def add_document_to_case(
        self,
        case_id: str,
        document_id: str,
        display_order: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Dict:
        """
        Add a document to a case
        
        Args:
            case_id: Case UUID
            document_id: Document UUID
            display_order: Order in case (auto-assigned if None)
            notes: Optional notes about this document in the case
            
        Returns:
            Case document relationship data
        """
        # Get current max order if not specified
        if display_order is None:
            max_order_result = self.supabase.table("case_documents").select(
                "display_order"
            ).eq("case_id", case_id).order("display_order", desc=True).limit(1).execute()
            
            if max_order_result.data:
                display_order = max_order_result.data[0]["display_order"] + 1
            else:
                display_order = 0
        
        case_doc_data = {
            "case_id": case_id,
            "document_id": document_id,
            "display_order": display_order,
            "notes": notes
        }
        
        result = self.supabase.table("case_documents").insert(case_doc_data).execute()
        return result.data[0] if result.data else None
    
    async def remove_document_from_case(
        self,
        case_id: str,
        document_id: str
    ) -> bool:
        """
        Remove a document from a case
        
        Args:
            case_id: Case UUID
            document_id: Document UUID
            
        Returns:
            True if removed successfully
        """
        result = self.supabase.table("case_documents").delete().eq(
            "case_id", case_id
        ).eq("document_id", document_id).execute()
        
        return len(result.data) > 0 if result.data else False
    
    async def reorder_documents(
        self,
        case_id: str,
        document_order: List[str]
    ) -> bool:
        """
        Reorder documents in a case
        
        Args:
            case_id: Case UUID
            document_order: List of document IDs in desired order
            
        Returns:
            True if reordered successfully
        """
        for index, document_id in enumerate(document_order):
            self.supabase.table("case_documents").update({
                "display_order": index
            }).eq("case_id", case_id).eq("document_id", document_id).execute()
        
        return True
    
    async def create_package(
        self,
        case_id: str,
        format: str = "zip"
    ) -> Dict:
        """
        Create a package export for a case
        
        Args:
            case_id: Case UUID
            format: Export format (zip or pdf)
            
        Returns:
            Package data
        """
        package_data = {
            "case_id": case_id,
            "format": format,
            "status": "pending"
        }
        
        result = self.supabase.table("packages").insert(package_data).execute()
        package = result.data[0] if result.data else None
        
        # Start package generation in background
        if package:
            await self._generate_package(package["id"], case_id, format)
        
        return package
    
    async def _generate_package(
        self,
        package_id: str,
        case_id: str,
        format: str
    ):
        """
        Generate package file (ZIP or PDF)
        
        Args:
            package_id: Package UUID
            case_id: Case UUID
            format: Export format
        """
        try:
            # Update status to processing
            self.supabase.table("packages").update({
                "status": "processing"
            }).eq("id", package_id).execute()
            
            # Get case and documents
            case = await self.get_case(case_id)
            
            if not case or not case.get("documents"):
                raise Exception("Case not found or has no documents")
            
            if format == "zip":
                file_path = await self._generate_zip(case)
            elif format == "pdf":
                file_path = await self._generate_pdf(case)
            else:
                raise Exception(f"Unsupported format: {format}")
            
            # Get file size
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            # Update package status
            self.supabase.table("packages").update({
                "status": "ready",
                "file_path": file_path,
                "file_size": file_size,
                "completed_at": datetime.utcnow().isoformat()
            }).eq("id", package_id).execute()
            
        except Exception as e:
            # Update status to failed
            self.supabase.table("packages").update({
                "status": "failed",
                "error_message": str(e)
            }).eq("id", package_id).execute()
    
    async def _generate_zip(self, case: Dict) -> str:
        """
        Generate ZIP file from case documents
        
        Args:
            case: Case data with documents
            
        Returns:
            File path to generated ZIP
        """
        # Create packages directory if it doesn't exist
        packages_dir = "/tmp/packages"
        os.makedirs(packages_dir, exist_ok=True)
        
        # Generate ZIP filename
        case_name_safe = "".join(c for c in case["name"] if c.isalnum() or c in (' ', '-', '_')).strip()
        zip_filename = f"{case_name_safe}_{case['id'][:8]}.zip"
        zip_path = os.path.join(packages_dir, zip_filename)
        
        # Create ZIP file
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add case metadata
            metadata = {
                "case_name": case["name"],
                "case_description": case.get("description", ""),
                "created_at": case["created_at"],
                "document_count": len(case["documents"]),
                "generated_at": datetime.utcnow().isoformat()
            }
            
            zipf.writestr("case_metadata.txt", 
                         f"Case: {metadata['case_name']}\n"
                         f"Description: {metadata['case_description']}\n"
                         f"Documents: {metadata['document_count']}\n"
                         f"Generated: {metadata['generated_at']}\n")
            
            # Add documents
            for doc_info in case["documents"]:
                doc = doc_info.get("documents", {})
                if not doc:
                    continue
                
                # Get document filename
                filename = doc.get("filename", f"document_{doc['id'][:8]}.txt")
                
                # Get document content
                content = doc.get("full_text", "")
                
                # Add to ZIP
                zipf.writestr(f"documents/{filename}", content)
                
                # Add document metadata
                doc_metadata = {
                    "filename": filename,
                    "document_type": doc.get("document_type", "unknown"),
                    "uploaded_at": doc.get("uploaded_at", ""),
                    "page_count": doc.get("page_count", 0),
                    "word_count": doc.get("word_count", 0),
                    "notes": doc_info.get("notes", "")
                }
                
                zipf.writestr(
                    f"metadata/{filename}.txt",
                    f"Filename: {doc_metadata['filename']}\n"
                    f"Type: {doc_metadata['document_type']}\n"
                    f"Uploaded: {doc_metadata['uploaded_at']}\n"
                    f"Pages: {doc_metadata['page_count']}\n"
                    f"Words: {doc_metadata['word_count']}\n"
                    f"Notes: {doc_metadata['notes']}\n"
                )
        
        return zip_path
    
    async def _generate_pdf(self, case: Dict) -> str:
        """
        Generate PDF binder from case documents
        
        Args:
            case: Case data with documents
            
        Returns:
            File path to generated PDF
        """
        # TODO: Implement PDF generation
        # For now, raise not implemented
        raise NotImplementedError("PDF generation not yet implemented")
    
    async def get_package(self, package_id: str) -> Optional[Dict]:
        """
        Get package by ID
        
        Args:
            package_id: Package UUID
            
        Returns:
            Package data
        """
        result = self.supabase.table("packages").select("*").eq("id", package_id).execute()
        return result.data[0] if result.data else None
    
    async def get_package_file_path(self, package_id: str) -> Optional[str]:
        """
        Get file path for a package
        
        Args:
            package_id: Package UUID
            
        Returns:
            File path if package is ready
        """
        package = await self.get_package(package_id)
        
        if not package or package["status"] != "ready":
            return None
        
        return package.get("file_path")


# Global instance - only create if supabase is available
if supabase:
    case_manager = CaseManager()
else:
    case_manager = None
