"""
Document Processor Module
Wraps existing document processing functionality for FastAPI
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
import hashlib

# Add legal-docs-system to path
sys.path.insert(0, "/home/ubuntu/legal-docs-system/processing")

from extractor import TextExtractor
from chunker import Chunker
from document_categorizer import DocumentCategorizer
from simple_entity_extractor import SimpleEntityExtractor
from entity_storage import EntityStorage

# Load environment
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


class DocumentProcessor:
    """Document processing service for API"""
    
    def __init__(self):
        self.extractor = TextExtractor()
        self.chunker = Chunker()
        self.categorizer = DocumentCategorizer()
        self.entity_extractor = SimpleEntityExtractor()
        self.entity_storage = EntityStorage()
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        
        # Load embedding model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def generate_embedding(self, text):
        """Generate 384-dimensional embedding"""
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def process(self, file_path, manual_category=None, manual_sub_category=None):
        """
        Process a document through the complete pipeline
        
        Returns:
            dict with document_id, filename, document_type, entities
        """
        try:
            # 1. Extract text
            full_text = self.extractor.extract(file_path)
            
            # 2. Categorize
            category_info = self.categorizer.categorize(
                filename=os.path.basename(file_path),
                content=full_text,
                manual_category=manual_category,
                manual_sub_category=manual_sub_category
            )
            document_type = category_info['document_type']
            
            # 3. Create document record
            doc_hash = hashlib.sha256(full_text.encode()).hexdigest()
            
            # Check if exists
            existing = self.supabase.table("documents").select("id").eq("filename", os.path.basename(file_path)).execute()
            if existing.data:
                return {
                    'document_id': existing.data[0]['id'],
                    'filename': os.path.basename(file_path),
                    'document_type': document_type,
                    'entities': []
                }
            
            document_record = {
                "filename": os.path.basename(file_path),
                "document_type": category_info['document_type'],
                "full_text": full_text,
                "file_hash": doc_hash,
                "metadata": {
                    "sub_category": category_info.get('sub_category'),
                    "category_confidence": category_info.get('category_confidence'),
                    "character_count": len(full_text),
                    "word_count": len(full_text.split())
                }
            }
            
            result = self.supabase.table("documents").insert(document_record).execute()
            document_id = result.data[0]['id']
            
            # 4. Chunk text
            chunk_metadata = {
                "document_id": document_id,
                "filename": os.path.basename(file_path)
            }
            chunks = self.chunker.chunk(full_text, chunk_metadata)
            
            # 5. Generate embeddings and insert chunks
            chunk_records = []
            for chunk in chunks:
                chunk_text = chunk.get('chunk_text') or chunk.get('text')
                embedding = self.generate_embedding(chunk_text)
                
                chunk_record = {
                    "document_id": document_id,
                    "chunk_index": chunk['chunk_index'],
                    "chunk_text": chunk_text,
                    "embedding": embedding,
                    "token_count": chunk.get('token_count', len(chunk_text.split())),
                    "start_char": chunk.get('start_char', 0),
                    "end_char": chunk.get('end_char', len(chunk_text)),
                    "metadata": chunk.get('metadata', {})
                }
                chunk_records.append(chunk_record)
            
            self.supabase.table("chunks").insert(chunk_records).execute()
            
            # 6. Extract entities
            entities = []
            try:
                entity_result = self.entity_extractor.extract_entities(full_text, document_type)
                if entity_result['success']:
                    entities = entity_result['entities']
                    self.entity_storage.store_entities(document_id, entities)
            except Exception as e:
                print(f"Entity extraction failed: {e}")
            
            return {
                'document_id': document_id,
                'filename': os.path.basename(file_path),
                'document_type': document_type,
                'entities': entities
            }
        
        except Exception as e:
            print(f"Processing failed: {e}")
            raise
    
    def list_documents(self, document_type=None, limit=50, offset=0):
        """List documents with optional filtering"""
        query = self.supabase.table("documents").select("id, filename, document_type, created_at, metadata")
        
        if document_type:
            query = query.eq("document_type", document_type)
        
        query = query.order("created_at", desc=True).limit(limit).offset(offset)
        result = query.execute()
        
        return result.data
    
    def get_document(self, document_id):
        """Get document details"""
        result = self.supabase.table("documents").select("*").eq("id", document_id).execute()
        
        if not result.data:
            return None
        
        return result.data[0]
    
    def delete_document(self, document_id):
        """Delete document and all chunks"""
        try:
            # Delete chunks first
            self.supabase.table("chunks").delete().eq("document_id", document_id).execute()
            
            # Delete document
            self.supabase.table("documents").delete().eq("id", document_id).execute()
            
            return True
        except:
            return False
