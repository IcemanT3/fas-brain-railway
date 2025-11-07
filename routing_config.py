"""
OneDrive Auto-Routing Configuration
Charter-compliant document routing based on entity extraction
"""

import os
import json
from typing import Dict, List, Optional

# Default routing configuration
# This maps entity types to OneDrive folder paths
DEFAULT_ROUTE_CONF = {
    "cases": {
        "arbitration_employment": {
            "path": "FAS_Brain/01_BY_CASE/arbitration_employment",
            "keywords": ["arbitration", "employment", "jams", "adr"],
            "entities": ["JAMS", "employment agreement"]
        },
        "derivative_lawsuit": {
            "path": "FAS_Brain/01_BY_CASE/derivative_lawsuit",
            "keywords": ["derivative", "shareholder", "fiduciary"],
            "entities": ["shareholder", "board of directors"]
        },
        "direct_lawsuit": {
            "path": "FAS_Brain/01_BY_CASE/direct_lawsuit",
            "keywords": ["complaint", "lawsuit", "plaintiff", "defendant"],
            "entities": []
        },
        "class_action": {
            "path": "FAS_Brain/01_BY_CASE/class_action",
            "keywords": ["class action", "class certification", "class members"],
            "entities": []
        },
        "regulatory_complaints": {
            "path": "FAS_Brain/01_BY_CASE/regulatory_complaints",
            "keywords": ["sec", "finra", "regulatory", "compliance"],
            "entities": ["SEC", "FINRA"]
        }
    },
    "issues": {
        "fraudulent_inducement": {
            "path": "FAS_Brain/02_BY_ISSUE/fraudulent_inducement",
            "keywords": ["fraud", "misrepresentation", "inducement", "reliance"],
            "entities": []
        },
        "breach_of_contract": {
            "path": "FAS_Brain/02_BY_ISSUE/breach_of_contract",
            "keywords": ["breach", "contract", "agreement", "violation"],
            "entities": []
        },
        "fiduciary_duty": {
            "path": "FAS_Brain/02_BY_ISSUE/fiduciary_duty",
            "keywords": ["fiduciary", "duty", "loyalty", "care"],
            "entities": []
        },
        "securities_fraud": {
            "path": "FAS_Brain/02_BY_ISSUE/securities_fraud",
            "keywords": ["securities", "fraud", "10b-5", "insider trading"],
            "entities": []
        }
    },
    "parties": {
        "trident": {
            "path": "FAS_Brain/03_BY_PARTY/trident",
            "keywords": ["trident"],
            "entities": ["Trident", "Trident Capital"]
        },
        "chris_johnson": {
            "path": "FAS_Brain/03_BY_PARTY/chris_johnson",
            "keywords": ["chris johnson", "christopher johnson"],
            "entities": ["Chris Johnson", "Christopher Johnson"]
        },
        "board_members": {
            "path": "FAS_Brain/03_BY_PARTY/board_members",
            "keywords": ["board", "director"],
            "entities": ["board of directors"]
        }
    }
}

class RoutingConfig:
    """Manages routing configuration for OneDrive auto-organization"""
    
    def __init__(self):
        """Initialize routing config from environment or defaults"""
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load routing config from ROUTE_CONF env var or use defaults"""
        route_conf_json = os.getenv("ROUTE_CONF")
        
        if route_conf_json:
            try:
                return json.loads(route_conf_json)
            except json.JSONDecodeError as e:
                print(f"⚠️  Invalid ROUTE_CONF JSON: {e}")
                print("Using default routing configuration")
        
        return DEFAULT_ROUTE_CONF
    
    def get_case_routes(self) -> Dict:
        """Get case routing configuration"""
        return self.config.get("cases", {})
    
    def get_issue_routes(self) -> Dict:
        """Get issue routing configuration"""
        return self.config.get("issues", {})
    
    def get_party_routes(self) -> Dict:
        """Get party routing configuration"""
        return self.config.get("parties", {})
    
    def get_all_routes(self) -> List[Dict]:
        """Get all routes as a flat list with metadata"""
        routes = []
        
        for category, items in self.config.items():
            for route_id, route_config in items.items():
                routes.append({
                    "id": route_id,
                    "category": category,
                    "path": route_config["path"],
                    "keywords": route_config.get("keywords", []),
                    "entities": route_config.get("entities", [])
                })
        
        return routes
    
    def get_inbox_path(self) -> str:
        """Get the inbox folder path"""
        return os.getenv("ONEDRIVE_INBOX_PATH", "FAS_Brain/00_INBOX")
    
    def get_vault_path(self) -> str:
        """Get the provenance vault path"""
        return os.getenv("ONEDRIVE_VAULT_PATH", "FAS_Brain/04_PROCESSED_ORIGINALS")
    
    def get_packages_path(self) -> str:
        """Get the case packages path"""
        return os.getenv("ONEDRIVE_PACKAGES_PATH", "FAS_Brain/05_CASE_PACKAGES")

# Global instance
routing_config = RoutingConfig()
