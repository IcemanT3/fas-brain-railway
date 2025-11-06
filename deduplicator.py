"""
Document Deduplication Module
Detects and handles duplicate documents using file hashing
"""
import os
import hashlib
from typing import Optional, Dict, List
from supabase import create_client, Client
from datetime import datetime

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rlhaxgpojdbflaeamhty.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None


class DocumentDeduplicator:
    """
    Handles document deduplication using SHA-256 file hashing
    """
    
    def __init__(self):
        if supabase is None:
            raise RuntimeError("Supabase client not initialized")
        self.supabase = supabase
    
    def calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA-256 hash of a file
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hexadecimal hash string
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def calculate_content_hash(self, content: bytes) -> str:
        """
        Calculate SHA-256 hash of file content
        
        Args:
            content: File content as bytes
            
        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(content).hexdigest()
    
    async def check_duplicate(self, file_hash: str) -> Optional[Dict]:
        """
        Check if a document with the same hash already exists
        
        Args:
            file_hash: SHA-256 hash of the file
            
        Returns:
            Existing document record if found, None otherwise
        """
        result = self.supabase.table('documents').select('*').eq(
            'file_hash', file_hash
        ).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        
        return None
    
    async def find_duplicates(self) -> List[Dict]:
        """
        Find all duplicate documents in the database
        
        Returns:
            List of duplicate document groups
        """
        # Query to find documents with duplicate hashes
        result = self.supabase.rpc(
            'find_duplicate_documents'
        ).execute()
        
        if result.data:
            return result.data
        
        return []
    
    async def get_duplicate_groups(self) -> List[Dict]:
        """
        Get all documents grouped by their file hash
        
        Returns:
            List of duplicate groups with document details
        """
        # Get all documents
        result = self.supabase.table('documents').select('*').execute()
        
        if not result.data:
            return []
        
        # Group by file_hash
        hash_groups = {}
        for doc in result.data:
            file_hash = doc.get('file_hash')
            if file_hash:
                if file_hash not in hash_groups:
                    hash_groups[file_hash] = []
                hash_groups[file_hash].append(doc)
        
        # Filter to only groups with duplicates
        duplicate_groups = [
            {
                'file_hash': file_hash,
                'count': len(docs),
                'documents': docs
            }
            for file_hash, docs in hash_groups.items()
            if len(docs) > 1
        ]
        
        return duplicate_groups
    
    async def merge_duplicates(
        self,
        keep_document_id: str,
        remove_document_ids: List[str]
    ) -> Dict:
        """
        Merge duplicate documents by keeping one and removing others
        
        Args:
            keep_document_id: ID of document to keep
            remove_document_ids: IDs of documents to remove
            
        Returns:
            Summary of merge operation
        """
        merged_count = 0
        errors = []
        
        for remove_id in remove_document_ids:
            try:
                # Update references in chunks table
                self.supabase.table('chunks').update({
                    'document_id': keep_document_id
                }).eq('document_id', remove_id).execute()
                
                # Update references in document_metadata table
                self.supabase.table('document_metadata').update({
                    'document_id': keep_document_id
                }).eq('document_id', remove_id).execute()
                
                # Update references in case_documents table
                self.supabase.table('case_documents').update({
                    'document_id': keep_document_id
                }).eq('document_id', remove_id).execute()
                
                # Delete the duplicate document
                self.supabase.table('documents').delete().eq(
                    'id', remove_id
                ).execute()
                
                merged_count += 1
                
            except Exception as e:
                errors.append({
                    'document_id': remove_id,
                    'error': str(e)
                })
        
        return {
            'kept_document_id': keep_document_id,
            'merged_count': merged_count,
            'errors': errors
        }
    
    async def mark_as_duplicate(
        self,
        document_id: str,
        original_document_id: str
    ) -> bool:
        """
        Mark a document as a duplicate of another
        
        Args:
            document_id: ID of the duplicate document
            original_document_id: ID of the original document
            
        Returns:
            True if successful
        """
        try:
            self.supabase.table('documents').update({
                'is_duplicate': True,
                'original_document_id': original_document_id,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', document_id).execute()
            
            return True
        except Exception as e:
            print(f"Error marking document as duplicate: {e}")
            return False
    
    async def get_deduplication_stats(self) -> Dict:
        """
        Get statistics about document deduplication
        
        Returns:
            Dictionary with deduplication statistics
        """
        # Get total documents
        total_result = self.supabase.table('documents').select(
            'id', count='exact'
        ).execute()
        total_documents = total_result.count if total_result.count else 0
        
        # Get duplicate groups
        duplicate_groups = await self.get_duplicate_groups()
        
        # Calculate stats
        duplicate_count = sum(
            group['count'] - 1 for group in duplicate_groups
        )
        unique_count = total_documents - duplicate_count
        
        return {
            'total_documents': total_documents,
            'unique_documents': unique_count,
            'duplicate_documents': duplicate_count,
            'duplicate_groups': len(duplicate_groups),
            'space_wasted_percentage': (
                (duplicate_count / total_documents * 100)
                if total_documents > 0 else 0
            )
        }


# Global instance
if supabase:
    deduplicator = DocumentDeduplicator()
else:
    deduplicator = None
