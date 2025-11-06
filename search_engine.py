"""
Search Engine Module
Wraps existing search functionality for FastAPI
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, "/home/ubuntu/legal-docs-system/retrieval")

from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import numpy as np

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

client = OpenAI()


class SearchEngine:
    """Enhanced search with entity filtering"""
    
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def search(
        self,
        query: str,
        entity_filter: str = None,
        entity_type_filter: str = None,
        document_type_filter: str = None,
        top_k: int = 10,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3
    ):
        """Enhanced hybrid search with entity filtering"""
        
        # Step 1: Get document IDs matching entity filter (if provided)
        filtered_doc_ids = None
        if entity_filter or entity_type_filter:
            filtered_doc_ids = self._get_documents_by_entity(entity_filter, entity_type_filter)
            
            if not filtered_doc_ids:
                return []
        
        # Step 2: Get all chunks
        chunks_query = self.supabase.table("chunks").select("*, documents!inner(filename, document_type, metadata)")
        
        if filtered_doc_ids:
            chunks_query = chunks_query.in_("document_id", filtered_doc_ids)
        
        if document_type_filter:
            chunks_query = chunks_query.eq("documents.document_type", document_type_filter)
        
        chunks_result = chunks_query.execute()
        chunks = chunks_result.data
        
        if not chunks:
            return []
        
        # Step 3: Vector search
        query_embedding = self.embedding_model.encode(query, convert_to_numpy=True)
        
        vector_scores = {}
        for chunk in chunks:
            if chunk['embedding']:
                if isinstance(chunk['embedding'], str):
                    embedding = np.array(eval(chunk['embedding']))
                else:
                    embedding = np.array(chunk['embedding'])
                
                similarity = np.dot(query_embedding, embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
                )
                vector_scores[chunk['id']] = float(similarity)
        
        # Step 4: Keyword search
        keywords = query.lower().split()
        keyword_scores = {}
        
        for chunk in chunks:
            text_lower = chunk['chunk_text'].lower()
            matches = sum(1 for keyword in keywords if keyword in text_lower)
            if matches > 0:
                keyword_scores[chunk['id']] = matches / len(keywords)
        
        # Step 5: Combine scores
        combined_scores = {}
        all_chunk_ids = set(vector_scores.keys()) | set(keyword_scores.keys())
        
        for chunk_id in all_chunk_ids:
            vector_score = vector_scores.get(chunk_id, 0)
            keyword_score = keyword_scores.get(chunk_id, 0)
            
            combined_score = (vector_score * vector_weight) + (keyword_score * keyword_weight)
            
            if chunk_id in vector_scores and chunk_id in keyword_scores:
                combined_score *= 1.2
            
            combined_scores[chunk_id] = combined_score
        
        # Step 6: Sort and get top results
        sorted_chunks = sorted(
            combined_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        # Step 7: Build result objects
        results = []
        chunk_dict = {c['id']: c for c in chunks}
        
        for chunk_id, score in sorted_chunks:
            chunk = chunk_dict[chunk_id]
            
            doc_metadata = chunk['documents']['metadata'] or {}
            entities = doc_metadata.get('entities', [])
            
            result = {
                'chunk_id': chunk_id,
                'document_id': chunk['document_id'],
                'filename': chunk['documents']['filename'],
                'document_type': chunk['documents']['document_type'],
                'chunk_text': chunk['chunk_text'],
                'chunk_index': chunk['chunk_index'],
                'score': score,
                'vector_score': vector_scores.get(chunk_id, 0),
                'keyword_score': keyword_scores.get(chunk_id, 0),
                'source': self._get_source_type(chunk_id, vector_scores, keyword_scores),
                'entities': entities
            }
            results.append(result)
        
        return results
    
    def _get_documents_by_entity(self, entity_name=None, entity_type=None):
        """Get document IDs that contain specified entities"""
        docs = self.supabase.table("documents").select("id, metadata").execute()
        
        matching_doc_ids = []
        for doc in docs.data:
            metadata = doc.get('metadata', {}) or {}
            entities = metadata.get('entities', [])
            
            for entity in entities:
                if entity_name:
                    entity_name_str = str(entity.get('name', ''))
                    if entity_name.lower() in entity_name_str.lower():
                        matching_doc_ids.append(doc['id'])
                        break
                
                if entity_type and entity.get('type') == entity_type:
                    matching_doc_ids.append(doc['id'])
                    break
        
        return matching_doc_ids
    
    def _get_source_type(self, chunk_id, vector_scores, keyword_scores):
        """Determine how chunk was found"""
        in_vector = chunk_id in vector_scores
        in_keyword = chunk_id in keyword_scores
        
        if in_vector and in_keyword:
            return "BOTH"
        elif in_vector:
            return "vector"
        else:
            return "keyword"
    
    def generate_answer(self, query: str, results: list, max_context_chunks: int = 5):
        """Generate AI answer from search results"""
        if not results:
            return "No relevant information found."
        
        context_parts = []
        for i, result in enumerate(results[:max_context_chunks]):
            context_parts.append(
                f"[Chunk {i+1} from {result['filename']}]\n{result['chunk_text']}"
            )
        
        context = "\n\n".join(context_parts)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a legal document analyst. Answer questions based on the provided context. Cite chunk numbers in your answer."},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        return response.choices[0].message.content
