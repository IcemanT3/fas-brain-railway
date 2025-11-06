"""
Entity Manager Module
Wraps entity functionality for FastAPI
"""

import os
from dotenv import load_dotenv
from supabase import create_client
from collections import Counter

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


class EntityManager:
    """Entity management service for API"""
    
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    def list_entities(self, entity_type=None, document_id=None):
        """List all entities with optional filtering"""
        docs = self.supabase.table("documents").select("id, filename, metadata").execute()
        
        all_entities = []
        
        for doc in docs.data:
            if document_id and doc['id'] != document_id:
                continue
            
            metadata = doc.get('metadata', {}) or {}
            entities = metadata.get('entities', [])
            
            for entity in entities:
                if entity_type and entity.get('type') != entity_type:
                    continue
                
                entity_info = {
                    'name': entity.get('name'),
                    'type': entity.get('type'),
                    'document_id': doc['id'],
                    'filename': doc['filename']
                }
                all_entities.append(entity_info)
        
        return all_entities
    
    def get_statistics(self):
        """Get entity statistics by type"""
        docs = self.supabase.table("documents").select("metadata").execute()
        
        entity_counts = Counter()
        total_entities = 0
        
        for doc in docs.data:
            metadata = doc.get('metadata', {}) or {}
            entities = metadata.get('entities', [])
            
            for entity in entities:
                entity_type = entity.get('type')
                if entity_type:
                    entity_counts[entity_type] += 1
                    total_entities += 1
        
        return {
            'total': total_entities,
            'by_type': dict(entity_counts),
            'types': list(entity_counts.keys())
        }
