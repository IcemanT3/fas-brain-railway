#!/usr/bin/env python3
"""
Simple Entity Extractor using OpenAI
Backup/alternative to Cognee for reliable entity extraction
"""

import os
import json
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")

client = OpenAI()


class SimpleEntityExtractor:
    """Extract entities using OpenAI GPT"""
    
    def __init__(self, model="gpt-4.1-mini"):
        self.model = model
    
    def extract_entities(self, text: str, document_type: str = "legal_document") -> Dict:
        """
        Extract entities from text using OpenAI
        
        Args:
            text: Document text
            document_type: Type of document (helps with context)
        
        Returns:
            Dictionary with entities and relationships
        """
        prompt = f"""Extract all entities from this {document_type}. Return a JSON object with:
- "people": list of people with {{name, role, description}}
- "organizations": list of organizations with {{name, type, description}}
- "locations": list of locations with {{name, description}}
- "dates": list of important dates with {{date, event, description}}
- "amounts": list of financial amounts with {{amount, currency, context}}
- "events": list of key events with {{event, date, description}}

For legal documents, focus on:
- Parties (plaintiffs, defendants, attorneys, judges)
- Legal entities (courts, law firms, companies)
- Case numbers, filing dates, hearing dates
- Monetary amounts (damages, fees, settlements)
- Key legal events (motions, rulings, judgments)

Return ONLY valid JSON, no other text.

Document text:
{text[:4000]}"""  # Limit to 4000 chars to avoid token limits
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a legal document analyst. Extract entities accurately and return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
                result_text = result_text.strip()
            
            entities = json.loads(result_text)
            
            # Flatten into single list with types
            all_entities = []
            
            for person in entities.get('people', []):
                all_entities.append({
                    'name': person.get('name'),
                    'type': 'person',
                    'description': person.get('description') or person.get('role', '')
                })
            
            for org in entities.get('organizations', []):
                all_entities.append({
                    'name': org.get('name'),
                    'type': 'organization',
                    'description': org.get('description') or org.get('type', '')
                })
            
            for loc in entities.get('locations', []):
                all_entities.append({
                    'name': loc.get('name'),
                    'type': 'location',
                    'description': loc.get('description', '')
                })
            
            for date in entities.get('dates', []):
                all_entities.append({
                    'name': date.get('date'),
                    'type': 'date',
                    'description': date.get('event') or date.get('description', '')
                })
            
            for amount in entities.get('amounts', []):
                all_entities.append({
                    'name': amount.get('amount'),
                    'type': 'amount',
                    'description': amount.get('context', '')
                })
            
            for event in entities.get('events', []):
                all_entities.append({
                    'name': event.get('event'),
                    'type': 'event',
                    'description': event.get('description', '')
                })
            
            return {
                'entities': all_entities,
                'count': len(all_entities),
                'success': True
            }
            
        except Exception as e:
            print(f"  ❌ Entity extraction failed: {e}")
            return {
                'entities': [],
                'count': 0,
                'success': False,
                'error': str(e)
            }


# Example usage
if __name__ == "__main__":
    extractor = SimpleEntityExtractor()
    
    sample_text = """
    MOTION TO DISMISS
    Case No: 2025-CV-12345
    
    John Smith, Plaintiff, filed a complaint against ABC Corporation
    on January 15, 2025. Attorney Jane Doe represents the Defendant.
    The contract was executed on March 1, 2024, for $500,000.
    The property is located at 123 Main Street, Orlando, Florida.
    """
    
    result = extractor.extract_entities(sample_text, "legal_document")
    
    print(f"\nExtracted {result['count']} entities:")
    for entity in result['entities']:
        print(f"  • {entity['name']} ({entity['type']})")
        if entity['description']:
            print(f"    {entity['description']}")
