"""
Document Organizer - Automatically organize documents into OneDrive folders
"""

import os
from typing import List, Dict, Optional
from openai import OpenAI

class DocumentOrganizer:
    """Organize documents into multiple folder views based on AI analysis"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Define legal cases
        self.cases = [
            "arbitration_employment",
            "derivative_lawsuit",
            "direct_lawsuit",
            "class_action",
            "regulatory_complaints"
        ]
        
        # Define legal issues
        self.issues = [
            "fraudulent_inducement",
            "breach_of_contract",
            "fiduciary_duty",
            "securities_fraud",
            "misrepresentation",
            "breach_of_fiduciary_duty"
        ]
        
        # Define parties
        self.parties = [
            "trident",
            "chris_johnson",
            "board_members",
            "oir",
            "fascorp"
        ]
    
    def analyze_document(self, filename: str, content: str) -> Dict:
        """
        Use AI to analyze document and determine organization
        
        Returns:
            {
                "cases": ["arbitration_employment", ...],
                "issues": ["fraudulent_inducement", ...],
                "parties": ["trident", ...],
                "document_type": "email|memo|court_filing|contract|...",
                "key_dates": ["2024-01-15", ...],
                "summary": "Brief summary of document"
            }
        """
        
        prompt = f"""Analyze this legal document and extract organization metadata.

Filename: {filename}

Content (first 3000 chars):
{content[:3000]}

Extract the following information:

1. **Cases**: Which of these legal cases does this document relate to? (can be multiple)
   - arbitration_employment
   - derivative_lawsuit
   - direct_lawsuit
   - class_action
   - regulatory_complaints

2. **Issues**: Which legal issues does this document address? (can be multiple)
   - fraudulent_inducement
   - breach_of_contract
   - fiduciary_duty
   - securities_fraud
   - misrepresentation
   - breach_of_fiduciary_duty

3. **Parties**: Which parties/entities are mentioned or involved? (can be multiple)
   - trident (Trident Capital)
   - chris_johnson (Chris Johnson)
   - board_members (Board members)
   - oir (Office of Insurance Regulation)
   - fascorp (FASCorp)

4. **Document Type**: What type of document is this?
   - email, memo, court_filing, contract, affidavit, deposition, correspondence, regulatory_filing, evidence, other

5. **Key Dates**: Extract any important dates mentioned (YYYY-MM-DD format)

6. **Summary**: Write a 2-3 sentence summary of the document's content and significance

Return your analysis in this exact JSON format:
{{
    "cases": ["case1", "case2"],
    "issues": ["issue1", "issue2"],
    "parties": ["party1", "party2"],
    "document_type": "type",
    "key_dates": ["2024-01-15", "2024-02-20"],
    "summary": "Your summary here"
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a legal document analyst. Extract metadata accurately and return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"Error analyzing document: {e}")
            # Return default structure
            return {
                "cases": [],
                "issues": [],
                "parties": [],
                "document_type": "other",
                "key_dates": [],
                "summary": "Analysis failed"
            }
    
    def get_organization_paths(self, analysis: Dict, filename: str) -> Dict[str, List[str]]:
        """
        Generate OneDrive paths where this document should be placed
        
        Returns:
            {
                "by_case": ["01_BY_CASE/arbitration_employment/filename.pdf", ...],
                "by_issue": ["02_BY_ISSUE/fraudulent_inducement/filename.pdf", ...],
                "by_party": ["03_BY_PARTY/trident/filename.pdf", ...]
            }
        """
        
        paths = {
            "by_case": [],
            "by_issue": [],
            "by_party": []
        }
        
        # Generate case paths
        for case in analysis.get("cases", []):
            if case in self.cases:
                paths["by_case"].append(f"01_BY_CASE/{case}/{filename}")
        
        # Generate issue paths
        for issue in analysis.get("issues", []):
            if issue in self.issues:
                paths["by_issue"].append(f"02_BY_ISSUE/{issue}/{filename}")
        
        # Generate party paths
        for party in analysis.get("parties", []):
            if party in self.parties:
                paths["by_party"].append(f"03_BY_PARTY/{party}/{filename}")
        
        return paths
    
    def organize_document(self, filename: str, content: str, onedrive_manager) -> Dict:
        """
        Complete organization workflow:
        1. Analyze document
        2. Determine folder paths
        3. Upload to multiple OneDrive locations
        4. Move original to archive
        
        Returns:
            {
                "analysis": {...},
                "paths": {...},
                "success": True/False
            }
        """
        
        # Analyze document
        analysis = self.analyze_document(filename, content)
        
        # Get organization paths
        paths = self.get_organization_paths(analysis, filename)
        
        # Upload to all relevant folders
        temp_file = f"/tmp/{filename}"
        try:
            # Save content to temp file
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Upload to all case folders
            for path in paths["by_case"]:
                onedrive_manager.upload_file(temp_file, path)
            
            # Upload to all issue folders
            for path in paths["by_issue"]:
                onedrive_manager.upload_file(temp_file, path)
            
            # Upload to all party folders
            for path in paths["by_party"]:
                onedrive_manager.upload_file(temp_file, path)
            
            # Move original to archive
            archive_path = f"04_PROCESSED_ORIGINALS/{filename}"
            onedrive_manager.move_file(f"00_INBOX/{filename}", "04_PROCESSED_ORIGINALS")
            
            # Clean up temp file
            os.remove(temp_file)
            
            return {
                "analysis": analysis,
                "paths": paths,
                "success": True
            }
            
        except Exception as e:
            print(f"Error organizing document: {e}")
            return {
                "analysis": analysis,
                "paths": paths,
                "success": False,
                "error": str(e)
            }
