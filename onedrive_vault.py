"""
OneDrive Vault Manager - Provenance vault and case package export
Charter-compliant document archival and case package generation
"""

import os
import hashlib
import json
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

class OneDriveVault:
    """Manages provenance vault and case package exports to OneDrive"""
    
    def __init__(self, onedrive_manager):
        """
        Initialize vault manager
        
        Args:
            onedrive_manager: OneDriveManager instance for file operations
        """
        self.onedrive = onedrive_manager
        self.vault_path = os.getenv("ONEDRIVE_VAULT_PATH", "FAS_Brain/04_PROCESSED_ORIGINALS")
        self.packages_path = os.getenv("ONEDRIVE_PACKAGES_PATH", "FAS_Brain/05_CASE_PACKAGES")
    
    def archive_to_vault(
        self,
        file_path: str,
        filename: str,
        file_hash: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Archive document to provenance vault
        
        Charter requirement: All processed documents must be archived with:
        - Original file preserved
        - SHA-256 hash for integrity
        - Metadata for audit trail
        - Immutable storage (no overwrites)
        
        Args:
            file_path: Local path to file
            filename: Original filename
            file_hash: SHA-256 hash of file
            metadata: Optional metadata dict
        
        Returns:
            Dict with vault_path, vault_url, and archive_id
        """
        # Create vault filename with hash prefix for uniqueness
        # Format: {hash[:8]}_{filename}
        vault_filename = f"{file_hash[:8]}_{filename}"
        vault_folder_path = f"{self.vault_path}/{file_hash[:2]}"  # Shard by first 2 chars of hash
        
        # Check if already archived
        existing = self._check_vault_exists(vault_folder_path, vault_filename)
        if existing:
            return {
                'status': 'already_archived',
                'vault_path': f"{vault_folder_path}/{vault_filename}",
                'vault_url': existing.get('webUrl'),
                'archive_id': file_hash
            }
        
        # Upload to vault
        try:
            # Ensure vault folder exists
            self.onedrive.create_folder(vault_folder_path)
            
            # Upload file
            upload_result = self.onedrive.upload_file(
                file_path,
                f"{vault_folder_path}/{vault_filename}"
            )
            
            # Create metadata sidecar file
            if metadata:
                metadata_content = json.dumps({
                    'original_filename': filename,
                    'file_hash': file_hash,
                    'archived_at': datetime.utcnow().isoformat(),
                    'metadata': metadata
                }, indent=2)
                
                metadata_filename = f"{vault_filename}.metadata.json"
                metadata_path = f"/tmp/{metadata_filename}"
                
                with open(metadata_path, 'w') as f:
                    f.write(metadata_content)
                
                self.onedrive.upload_file(
                    metadata_path,
                    f"{vault_folder_path}/{metadata_filename}"
                )
                
                os.remove(metadata_path)
            
            return {
                'status': 'archived',
                'vault_path': f"{vault_folder_path}/{vault_filename}",
                'vault_url': upload_result.get('webUrl'),
                'archive_id': file_hash
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _check_vault_exists(self, folder_path: str, filename: str) -> Optional[Dict]:
        """Check if file already exists in vault"""
        try:
            files = self.onedrive.list_files(folder_path)
            for file_info in files:
                if file_info.get('name') == filename:
                    return file_info
        except:
            pass
        return None
    
    def create_case_package(
        self,
        case_id: str,
        case_name: str,
        documents: List[Dict],
        summary: Optional[str] = None,
        timeline: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Create comprehensive case package in OneDrive
        
        Charter requirement: Case packages must include:
        - All relevant documents
        - Case summary
        - Timeline of events
        - Factual record
        - Attorney-ready format (Markdown → PDF)
        
        Args:
            case_id: Case identifier
            case_name: Human-readable case name
            documents: List of document dicts with id, filename, text_content
            summary: Optional case summary
            timeline: Optional timeline events
        
        Returns:
            Dict with package_path, package_url, and file_list
        """
        # Create case package folder
        package_folder = f"{self.packages_path}/{case_id}_{case_name.replace(' ', '_')}"
        
        try:
            # Ensure package folder exists
            self.onedrive.create_folder(package_folder)
            
            # 1. Create case summary document
            if summary:
                summary_md = self._generate_summary_markdown(
                    case_name,
                    summary,
                    timeline,
                    documents
                )
                
                summary_path = f"/tmp/case_summary_{case_id}.md"
                with open(summary_path, 'w') as f:
                    f.write(summary_md)
                
                self.onedrive.upload_file(
                    summary_path,
                    f"{package_folder}/00_CASE_SUMMARY.md"
                )
                
                os.remove(summary_path)
            
            # 2. Create timeline document
            if timeline:
                timeline_md = self._generate_timeline_markdown(timeline)
                
                timeline_path = f"/tmp/timeline_{case_id}.md"
                with open(timeline_path, 'w') as f:
                    f.write(timeline_md)
                
                self.onedrive.upload_file(
                    timeline_path,
                    f"{package_folder}/01_TIMELINE.md"
                )
                
                os.remove(timeline_path)
            
            # 3. Create documents folder and copy source documents
            docs_folder = f"{package_folder}/02_SOURCE_DOCUMENTS"
            self.onedrive.create_folder(docs_folder)
            
            uploaded_docs = []
            for i, doc in enumerate(documents):
                doc_filename = doc.get('filename', f'document_{i+1}.txt')
                
                # If we have the original file, copy it
                # Otherwise create a text file with the content
                if doc.get('file_path') and os.path.exists(doc['file_path']):
                    self.onedrive.upload_file(
                        doc['file_path'],
                        f"{docs_folder}/{doc_filename}"
                    )
                elif doc.get('text_content'):
                    # Create text file
                    temp_path = f"/tmp/doc_{i}_{doc_filename}.txt"
                    with open(temp_path, 'w') as f:
                        f.write(doc['text_content'])
                    
                    self.onedrive.upload_file(
                        temp_path,
                        f"{docs_folder}/{doc_filename}.txt"
                    )
                    
                    os.remove(temp_path)
                
                uploaded_docs.append(doc_filename)
            
            # 4. Create package manifest
            manifest = {
                'case_id': case_id,
                'case_name': case_name,
                'created_at': datetime.utcnow().isoformat(),
                'document_count': len(documents),
                'documents': uploaded_docs,
                'has_summary': summary is not None,
                'has_timeline': timeline is not None
            }
            
            manifest_path = f"/tmp/manifest_{case_id}.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            self.onedrive.upload_file(
                manifest_path,
                f"{package_folder}/MANIFEST.json"
            )
            
            os.remove(manifest_path)
            
            return {
                'status': 'success',
                'package_path': package_folder,
                'package_url': f"https://onedrive.com/...",  # TODO: Get actual URL
                'file_count': len(uploaded_docs) + 2  # +2 for summary and timeline
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _generate_summary_markdown(
        self,
        case_name: str,
        summary: str,
        timeline: Optional[List[Dict]],
        documents: List[Dict]
    ) -> str:
        """Generate case summary in Markdown format"""
        md = f"# Case Summary: {case_name}\n\n"
        md += f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        md += "---\n\n"
        
        md += "## Executive Summary\n\n"
        md += f"{summary}\n\n"
        
        if timeline:
            md += "## Key Events\n\n"
            md += f"See `01_TIMELINE.md` for detailed timeline.\n\n"
        
        md += "## Source Documents\n\n"
        md += f"Total documents: {len(documents)}\n\n"
        
        for i, doc in enumerate(documents, 1):
            md += f"{i}. {doc.get('filename', 'Unknown')}\n"
        
        md += "\n---\n\n"
        md += "*This case package was generated by FAS Brain Document Intelligence Hub*\n"
        
        return md
    
    def _generate_timeline_markdown(self, timeline: List[Dict]) -> str:
        """Generate timeline in Markdown format"""
        md = "# Case Timeline\n\n"
        md += f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        md += "---\n\n"
        
        # Sort by date
        sorted_timeline = sorted(timeline, key=lambda x: x.get('date', ''))
        
        for event in sorted_timeline:
            date = event.get('date', 'Unknown date')
            description = event.get('description', '')
            source = event.get('source', '')
            
            md += f"### {date}\n\n"
            md += f"{description}\n\n"
            
            if source:
                md += f"*Source: {source}*\n\n"
            
            md += "---\n\n"
        
        return md
