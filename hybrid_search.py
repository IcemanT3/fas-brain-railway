"""
Hybrid Search Module
Combines full-text search (PostgreSQL) with vector search (pgvector) and re-ranking
"""
import os
from typing import List, Dict, Optional
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rlhaxgpojdbflaeamhty.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None


class HybridSearch:
    """
    Implements hybrid search combining:
    1. Full-text search (PostgreSQL tsvector)
    2. Vector similarity search (pgvector)
    3. Re-ranking based on combined scores
    """
    
    def __init__(self):
        if supabase is None:
            raise RuntimeError("Supabase client not initialized")
        self.supabase = supabase
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
        vector_weight: float = 0.6,
        fulltext_weight: float = 0.4,
        entity_filter: Optional[str] = None,
        entity_type_filter: Optional[str] = None,
        document_type_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Perform hybrid search combining vector and full-text search
        
        Args:
            query: Search query string
            top_k: Number of results to return
            vector_weight: Weight for vector similarity score (0-1)
            fulltext_weight: Weight for full-text search score (0-1)
            entity_filter: Filter by entity name
            entity_type_filter: Filter by entity type
            document_type_filter: Filter by document type
            
        Returns:
            List of search results with combined scores
        """
        # Generate query embedding
        query_embedding = self.model.encode(query).tolist()
        
        # Perform vector search
        vector_results = await self._vector_search(
            query_embedding,
            top_k * 2,  # Get more results for re-ranking
            entity_filter,
            entity_type_filter,
            document_type_filter
        )
        
        # Perform full-text search
        fulltext_results = await self._fulltext_search(
            query,
            top_k * 2,
            entity_filter,
            entity_type_filter,
            document_type_filter
        )
        
        # Combine and re-rank results
        combined_results = self._combine_and_rerank(
            vector_results,
            fulltext_results,
            vector_weight,
            fulltext_weight
        )
        
        # Return top_k results
        return combined_results[:top_k]
    
    async def _vector_search(
        self,
        query_embedding: List[float],
        limit: int,
        entity_filter: Optional[str] = None,
        entity_type_filter: Optional[str] = None,
        document_type_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Perform vector similarity search using pgvector
        """
        # Build query
        query = self.supabase.rpc(
            'match_chunks',
            {
                'query_embedding': query_embedding,
                'match_count': limit
            }
        )
        
        # Apply filters if provided
        if document_type_filter:
            query = query.eq('document_type', document_type_filter)
        
        result = query.execute()
        
        # Normalize scores to 0-1 range
        results = []
        if result.data:
            max_similarity = max([r.get('similarity', 0) for r in result.data]) if result.data else 1
            for item in result.data:
                similarity = item.get('similarity', 0)
                normalized_score = similarity / max_similarity if max_similarity > 0 else 0
                results.append({
                    'chunk_id': item.get('id'),
                    'document_id': item.get('document_id'),
                    'content': item.get('content'),
                    'vector_score': normalized_score,
                    'metadata': item
                })
        
        return results
    
    async def _fulltext_search(
        self,
        query: str,
        limit: int,
        entity_filter: Optional[str] = None,
        entity_type_filter: Optional[str] = None,
        document_type_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Perform full-text search using PostgreSQL tsvector
        """
        # Use PostgreSQL full-text search
        # This requires a tsvector column and GIN index on the chunks table
        
        # For now, use simple text matching until tsvector is set up
        query_builder = self.supabase.table('chunks').select('*')
        
        # Apply text search
        query_builder = query_builder.ilike('content', f'%{query}%')
        
        # Apply filters
        if document_type_filter:
            query_builder = query_builder.eq('document_type', document_type_filter)
        
        query_builder = query_builder.limit(limit)
        
        result = query_builder.execute()
        
        # Calculate relevance scores based on query term frequency
        results = []
        if result.data:
            for item in result.data:
                content = item.get('content', '').lower()
                query_lower = query.lower()
                
                # Simple relevance scoring based on term frequency
                term_count = content.count(query_lower)
                # Normalize by content length
                relevance_score = min(term_count / (len(content.split()) / 100), 1.0)
                
                results.append({
                    'chunk_id': item.get('id'),
                    'document_id': item.get('document_id'),
                    'content': item.get('content'),
                    'fulltext_score': relevance_score,
                    'metadata': item
                })
        
        return results
    
    def _combine_and_rerank(
        self,
        vector_results: List[Dict],
        fulltext_results: List[Dict],
        vector_weight: float,
        fulltext_weight: float
    ) -> List[Dict]:
        """
        Combine results from vector and full-text search and re-rank
        """
        # Create a dictionary to merge results by chunk_id
        combined = {}
        
        # Add vector search results
        for result in vector_results:
            chunk_id = result['chunk_id']
            combined[chunk_id] = {
                **result,
                'vector_score': result.get('vector_score', 0),
                'fulltext_score': 0,
                'combined_score': 0
            }
        
        # Add full-text search results
        for result in fulltext_results:
            chunk_id = result['chunk_id']
            if chunk_id in combined:
                # Update existing entry
                combined[chunk_id]['fulltext_score'] = result.get('fulltext_score', 0)
            else:
                # Add new entry
                combined[chunk_id] = {
                    **result,
                    'vector_score': 0,
                    'fulltext_score': result.get('fulltext_score', 0),
                    'combined_score': 0
                }
        
        # Calculate combined scores
        for chunk_id in combined:
            vector_score = combined[chunk_id]['vector_score']
            fulltext_score = combined[chunk_id]['fulltext_score']
            combined_score = (vector_score * vector_weight) + (fulltext_score * fulltext_weight)
            combined[chunk_id]['combined_score'] = combined_score
        
        # Sort by combined score
        sorted_results = sorted(
            combined.values(),
            key=lambda x: x['combined_score'],
            reverse=True
        )
        
        return sorted_results
    
    async def search_with_context(
        self,
        query: str,
        top_k: int = 10,
        context_window: int = 2
    ) -> List[Dict]:
        """
        Search and return results with surrounding context chunks
        
        Args:
            query: Search query
            top_k: Number of results
            context_window: Number of chunks before/after to include
            
        Returns:
            Results with context
        """
        results = await self.search(query, top_k)
        
        # For each result, fetch surrounding chunks
        enriched_results = []
        for result in results:
            chunk_id = result['chunk_id']
            document_id = result['document_id']
            
            # Get chunk position
            chunk_result = self.supabase.table('chunks').select(
                'chunk_index'
            ).eq('id', chunk_id).execute()
            
            if chunk_result.data:
                chunk_index = chunk_result.data[0]['chunk_index']
                
                # Fetch surrounding chunks
                context_chunks = self.supabase.table('chunks').select('*').eq(
                    'document_id', document_id
                ).gte(
                    'chunk_index', max(0, chunk_index - context_window)
                ).lte(
                    'chunk_index', chunk_index + context_window
                ).order('chunk_index').execute()
                
                result['context_chunks'] = context_chunks.data if context_chunks.data else []
            
            enriched_results.append(result)
        
        return enriched_results


# Global instance
if supabase:
    hybrid_search = HybridSearch()
else:
    hybrid_search = None
