#!/usr/bin/env python3
"""
Entity Storage - Store extracted entities in Supabase
Uses existing documents table with JSONB metadata for simplicity
"""

import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment
load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


class EntityStorage:
    """Store and retrieve entities using Supabase"""
    
    def __init__(self):
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    def store_entities(
        self, 
        document_id: str, 
        entities: List[Dict],
        relationships: List[Dict] = None
    ):
        """
        Store entities for a document in its metadata
        
        Args:
            document_id: Document UUID
            entities: List of entities with name, type, description
            relationships: List of relationships between entities
        """
        try:
            # Get current document
            doc = self.supabase.table("documents").select("metadata").eq("id", document_id).execute()
            
            if not doc.data:
                print(f"  ⚠️  Document {document_id} not found")
                return False
            
            # Update metadata with entities
            metadata = doc.data[0].get('metadata', {}) or {}
            metadata['entities'] = entities
            if relationships:
                metadata['relationships'] = relationships
            metadata['entity_count'] = len(entities)
            metadata['has_knowledge_graph'] = True
            
            # Update document
            self.supabase.table("documents").update({
                'metadata': metadata
            }).eq('id', document_id).execute()
            
            print(f"  ✅ Stored {len(entities)} entities for document")
            return True
            
        except Exception as e:
            print(f"  ❌ Failed to store entities: {e}")
            return False
    
    def get_entities(self, document_id: str) -> List[Dict]:
        """
        Get entities for a document
        
        Args:
            document_id: Document UUID
        
        Returns:
            List of entities
        """
        try:
            doc = self.supabase.table("documents").select("metadata").eq("id", document_id).execute()
            
            if not doc.data:
                return []
            
            metadata = doc.data[0].get('metadata', {}) or {}
            return metadata.get('entities', [])
            
        except Exception as e:
            print(f"  ❌ Failed to get entities: {e}")
            return []
    
    def get_all_entities(self) -> List[Dict]:
        """
        Get all entities from all documents
        
        Returns:
            List of all entities with document info
        """
        try:
            docs = self.supabase.table("documents").select("id, filename, metadata").execute()
            
            all_entities = []
            for doc in docs.data:
                metadata = doc.get('metadata', {}) or {}
                entities = metadata.get('entities', [])
                
                for entity in entities:
                    all_entities.append({
                        **entity,
                        'document_id': doc['id'],
                        'document_filename': doc['filename']
                    })
            
            return all_entities
            
        except Exception as e:
            print(f"  ❌ Failed to get all entities: {e}")
            return []
    
    def search_entities(self, query: str, entity_type: str = None) -> List[Dict]:
        """
        Search for entities across all documents
        
        Args:
            query: Search query
            entity_type: Optional entity type filter
        
        Returns:
            List of matching entities
        """
        all_entities = self.get_all_entities()
        
        # Filter by query
        query_lower = query.lower()
        results = []
        
        for entity in all_entities:
            name = entity.get('name', '').lower()
            description = entity.get('description', '').lower()
            ent_type = entity.get('type', '')
            
            # Check if query matches
            if query_lower in name or query_lower in description:
                # Check type filter
                if entity_type is None or ent_type == entity_type:
                    results.append(entity)
        
        return results
    
    def get_entities_by_type(self, entity_type: str) -> List[Dict]:
        """
        Get all entities of a specific type
        
        Args:
            entity_type: Entity type (person, organization, etc.)
        
        Returns:
            List of entities of that type
        """
        all_entities = self.get_all_entities()
        return [e for e in all_entities if e.get('type') == entity_type]
    
    def get_document_parties(self, document_id: str) -> Dict:
        """
        Get all parties (people and organizations) in a document
        
        Args:
            document_id: Document UUID
        
        Returns:
            Dictionary with people and organizations
        """
        entities = self.get_entities(document_id)
        
        people = [e for e in entities if e.get('type') == 'person']
        organizations = [e for e in entities if e.get('type') == 'organization']
        
        return {
            'people': people,
            'organizations': organizations,
            'total': len(people) + len(organizations)
        }


# Example usage
if __name__ == "__main__":
    storage = EntityStorage()
    
    # Example: Store entities
    sample_entities = [
        {
            'name': 'John Smith',
            'type': 'person',
            'description': 'Plaintiff in the case'
        },
        {
            'name': 'ABC Corporation',
            'type': 'organization',
            'description': 'Defendant company'
        }
    ]
    
    # Get first document
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    docs = supabase.table("documents").select("id, filename").limit(1).execute()
    
    if docs.data:
        doc_id = docs.data[0]['id']
        print(f"Testing with document: {docs.data[0]['filename']}")
        
        # Store entities
        storage.store_entities(doc_id, sample_entities)
        
        # Retrieve entities
        entities = storage.get_entities(doc_id)
        print(f"\nRetrieved {len(entities)} entities:")
        for entity in entities:
            print(f"  - {entity['name']} ({entity['type']})")
        
        # Get parties
        parties = storage.get_document_parties(doc_id)
        print(f"\nParties in document:")
        print(f"  People: {len(parties['people'])}")
        print(f"  Organizations: {len(parties['organizations'])}")
