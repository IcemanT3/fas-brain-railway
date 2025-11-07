"""
Document Router - Entity-based routing logic for OneDrive auto-organization
Charter-compliant routing with scoring and audit trail
"""

from typing import Dict, List, Tuple, Optional
import re
from routing_config import routing_config

class DocumentRouter:
    """Routes documents to appropriate OneDrive folders based on entity extraction"""
    
    def __init__(self):
        """Initialize router with routing configuration"""
        self.config = routing_config
        self.routes = self.config.get_all_routes()
    
    def score_document(self, text: str, entities: Dict) -> List[Dict]:
        """
        Score document against all routing rules
        
        Args:
            text: Full document text (lowercased for matching)
            entities: Extracted entities dict with keys: persons, organizations, dates, etc.
        
        Returns:
            List of scored routes sorted by score (highest first)
            Each route has: {id, category, path, score, matches}
        """
        text_lower = text.lower()
        scored_routes = []
        
        for route in self.routes:
            score = 0
            matches = []
            
            # Score based on keyword matches (1 point per keyword)
            for keyword in route.get("keywords", []):
                if keyword.lower() in text_lower:
                    score += 1
                    matches.append(f"keyword:{keyword}")
            
            # Score based on entity matches (2 points per entity - more valuable)
            route_entities = route.get("entities", [])
            for route_entity in route_entities:
                # Check if entity appears in any extracted entity list
                entity_found = self._check_entity_match(route_entity, entities)
                if entity_found:
                    score += 2
                    matches.append(f"entity:{route_entity}")
            
            # Only include routes with non-zero score
            if score > 0:
                scored_routes.append({
                    "id": route["id"],
                    "category": route["category"],
                    "path": route["path"],
                    "score": score,
                    "matches": matches
                })
        
        # Sort by score (highest first)
        scored_routes.sort(key=lambda x: x["score"], reverse=True)
        
        return scored_routes
    
    def _check_entity_match(self, route_entity: str, entities: Dict) -> bool:
        """Check if route entity matches any extracted entity"""
        route_entity_lower = route_entity.lower()
        
        # Check all entity types
        for entity_type, entity_list in entities.items():
            if not isinstance(entity_list, list):
                continue
            
            for entity in entity_list:
                if isinstance(entity, str) and route_entity_lower in entity.lower():
                    return True
                elif isinstance(entity, dict) and "text" in entity:
                    if route_entity_lower in entity["text"].lower():
                        return True
        
        return False
    
    def get_routing_decisions(
        self, 
        text: str, 
        entities: Dict,
        threshold: float = 1.0
    ) -> List[Dict]:
        """
        Get routing decisions for a document
        
        Args:
            text: Full document text
            entities: Extracted entities
            threshold: Minimum score to include route (default 1.0)
        
        Returns:
            List of routes that meet threshold, sorted by score
        """
        scored_routes = self.score_document(text, entities)
        
        # Filter by threshold
        return [r for r in scored_routes if r["score"] >= threshold]
    
    def get_primary_routes(
        self,
        text: str,
        entities: Dict,
        max_routes: int = 3
    ) -> Dict[str, List[str]]:
        """
        Get primary routing destinations (top N routes per category)
        
        Args:
            text: Full document text
            entities: Extracted entities
            max_routes: Maximum routes per category (default 3)
        
        Returns:
            Dict with category -> list of folder paths
            Example: {"cases": ["path1", "path2"], "issues": ["path3"]}
        """
        scored_routes = self.score_document(text, entities)
        
        # Group by category
        by_category = {}
        for route in scored_routes:
            category = route["category"]
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(route["path"])
        
        # Limit to max_routes per category
        result = {}
        for category, paths in by_category.items():
            result[category] = paths[:max_routes]
        
        return result
    
    def create_audit_record(
        self,
        document_id: str,
        filename: str,
        scored_routes: List[Dict],
        selected_routes: List[str]
    ) -> Dict:
        """
        Create audit record for routing decision
        
        Args:
            document_id: Document ID
            filename: Original filename
            scored_routes: All scored routes
            selected_routes: Routes that were actually used
        
        Returns:
            Audit record dict
        """
        return {
            "document_id": document_id,
            "filename": filename,
            "timestamp": None,  # Will be set by caller
            "scored_routes": scored_routes,
            "selected_routes": selected_routes,
            "routing_version": "1.0"
        }

# Global instance
document_router = DocumentRouter()
