"""
Case Package Generator - Create comprehensive case summaries
"""

import os
from typing import List, Dict
from datetime import datetime
from openai import OpenAI

class CasePackageGenerator:
    """Generate comprehensive case packages combining all relevant documents"""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def get_documents_for_case(self, case_name: str) -> List[Dict]:
        """Get all documents related to a specific case"""
        # Query documents that have this case in their analysis
        response = self.supabase.table("documents").select("*").execute()
        
        case_docs = []
        for doc in response.data:
            metadata = doc.get("metadata", {})
            analysis = metadata.get("analysis", {})
            if case_name in analysis.get("cases", []):
                case_docs.append(doc)
        
        return case_docs
    
    def extract_timeline(self, documents: List[Dict]) -> List[Dict]:
        """Extract and sort timeline of events from documents"""
        timeline = []
        
        for doc in documents:
            metadata = doc.get("metadata", {})
            analysis = metadata.get("analysis", {})
            key_dates = analysis.get("key_dates", [])
            
            for date in key_dates:
                timeline.append({
                    "date": date,
                    "document": doc["filename"],
                    "summary": analysis.get("summary", "")
                })
        
        # Sort by date
        timeline.sort(key=lambda x: x["date"])
        
        return timeline
    
    def generate_case_summary(self, case_name: str, documents: List[Dict]) -> str:
        """Use AI to generate comprehensive case summary"""
        
        # Prepare document summaries
        doc_summaries = []
        for doc in documents:
            metadata = doc.get("metadata", {})
            analysis = metadata.get("analysis", {})
            doc_summaries.append(f"**{doc['filename']}**: {analysis.get('summary', 'No summary')}")
        
        summaries_text = "\n\n".join(doc_summaries)
        
        prompt = f"""Generate a comprehensive case summary for the {case_name.replace('_', ' ').title()} case.

You have {len(documents)} documents related to this case:

{summaries_text}

Create a comprehensive case summary that includes:

1. **Case Overview**: What is this case about? What are the main allegations/claims?

2. **Key Parties**: Who are the main parties involved and their roles?

3. **Core Issues**: What are the central legal issues at stake?

4. **Factual Background**: What are the key facts and events that led to this case?

5. **Current Status**: Based on the documents, what is the current state of this case?

6. **Key Evidence**: What are the most important pieces of evidence or documentation?

Write this as a professional legal summary that an attorney could use to quickly understand the case."""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a legal analyst creating comprehensive case summaries for attorneys."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error generating case summary: {e}")
            return "Error generating summary"
    
    def generate_case_package(self, case_name: str) -> str:
        """
        Generate complete case package as Markdown
        
        Returns:
            Markdown-formatted case package
        """
        
        # Get all documents for this case
        documents = self.get_documents_for_case(case_name)
        
        if not documents:
            return f"# {case_name.replace('_', ' ').title()}\n\nNo documents found for this case."
        
        # Extract timeline
        timeline = self.extract_timeline(documents)
        
        # Generate AI summary
        case_summary = self.generate_case_summary(case_name, documents)
        
        # Build Markdown package
        package = f"""# {case_name.replace('_', ' ').title()} - Case Package

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Documents**: {len(documents)}

---

## Executive Summary

{case_summary}

---

## Timeline of Events

"""
        
        # Add timeline
        for event in timeline:
            package += f"**{event['date']}** - {event['document']}\n"
            package += f"  {event['summary']}\n\n"
        
        package += "\n---\n\n## Document Index\n\n"
        
        # Add document index
        for i, doc in enumerate(documents, 1):
            metadata = doc.get("metadata", {})
            analysis = metadata.get("analysis", {})
            package += f"{i}. **{doc['filename']}**\n"
            package += f"   - Type: {analysis.get('document_type', 'Unknown')}\n"
            package += f"   - Summary: {analysis.get('summary', 'No summary')}\n"
            package += f"   - Issues: {', '.join(analysis.get('issues', []))}\n"
            package += f"   - Parties: {', '.join(analysis.get('parties', []))}\n\n"
        
        package += "\n---\n\n## Full Document Text\n\n"
        
        # Add full text of all documents
        for i, doc in enumerate(documents, 1):
            package += f"### Document {i}: {doc['filename']}\n\n"
            package += f"{doc.get('full_text', 'No text available')}\n\n"
            package += "---\n\n"
        
        return package
    
    def generate_all_case_packages(self) -> Dict[str, str]:
        """Generate case packages for all cases"""
        
        cases = [
            "arbitration_employment",
            "derivative_lawsuit",
            "direct_lawsuit",
            "class_action",
            "regulatory_complaints"
        ]
        
        packages = {}
        for case in cases:
            packages[case] = self.generate_case_package(case)
        
        return packages
    
    def save_package_to_onedrive(self, case_name: str, package_content: str, onedrive_manager):
        """Save case package to OneDrive"""
        
        # Save to temp file
        filename = f"{case_name}_package.md"
        temp_path = f"/tmp/{filename}"
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(package_content)
        
        # Upload to OneDrive
        onedrive_path = f"05_CASE_PACKAGES/{filename}"
        onedrive_manager.upload_file(temp_path, onedrive_path)
        
        # Clean up
        os.remove(temp_path)
        
        return onedrive_path
