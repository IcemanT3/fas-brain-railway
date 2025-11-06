#!/usr/bin/env python3
"""
Document Categorization System
Automatically categorizes legal documents into primary and sub-categories
"""

from typing import Dict, Optional, Tuple
import re

# Primary categories
PRIMARY_CATEGORIES = {
    'contract': 'Contracts and Agreements',
    'legal_document': 'Legal Documents and Court Filings',
    'ai_opinion': 'AI-Generated Analysis and Opinions',
    'evidence': 'Evidence and Supporting Documents',
    'correspondence': 'Correspondence and Communications',
    'recording': 'Recordings and Transcripts'
}

# Sub-categories for each primary category
SUB_CATEGORIES = {
    'contract': [
        'Operating Agreement',
        'Partnership Agreement',
        'Employment Contract',
        'Service Agreement',
        'Non-Disclosure Agreement (NDA)',
        'Purchase Agreement',
        'Lease Agreement',
        'Settlement Agreement',
        'Other Contract'
    ],
    'legal_document': [
        'Court Filing',
        'Motion',
        'Complaint',
        'Answer',
        'Judgment',
        'Order',
        'Discovery Request',
        'Discovery Response',
        'Brief',
        'Memorandum',
        'Notice',
        'Subpoena',
        'Affidavit',
        'Declaration',
        'Other Legal Document'
    ],
    'ai_opinion': [
        'Case Analysis',
        'Document Summary',
        'Risk Assessment',
        'Strategy Recommendation',
        'Timeline Analysis',
        'Contradiction Report',
        'Other AI Opinion'
    ],
    'evidence': [
        'Exhibit',
        'Photograph',
        'Financial Document',
        'Medical Record',
        'Expert Report',
        'Other Evidence'
    ],
    'correspondence': [
        'Email',
        'Letter',
        'Memo',
        'Text Message',
        'Other Correspondence'
    ],
    'recording': [
        'Deposition Transcript',
        'Hearing Transcript',
        'Trial Transcript',
        'Interview Transcript',
        'Audio Recording',
        'Video Recording',
        'Other Recording'
    ]
}

# Keywords for automatic categorization
CATEGORY_KEYWORDS = {
    'contract': [
        'agreement', 'contract', 'operating agreement', 'partnership',
        'employment', 'service agreement', 'nda', 'non-disclosure',
        'lease', 'purchase', 'settlement'
    ],
    'legal_document': [
        'court', 'motion', 'complaint', 'answer', 'judgment', 'order',
        'discovery', 'brief', 'memorandum', 'notice', 'subpoena',
        'affidavit', 'declaration', 'plaintiff', 'defendant', 'case no'
    ],
    'correspondence': [
        'email', 'letter', 'memo', 'from:', 'to:', 'subject:', 'dear'
    ],
    'recording': [
        'transcript', 'deposition', 'hearing', 'trial', 'testimony',
        'q:', 'a:', 'witness'
    ]
}

SUB_CATEGORY_KEYWORDS = {
    'Operating Agreement': ['operating agreement', 'llc agreement'],
    'Partnership Agreement': ['partnership agreement', 'partner'],
    'Employment Contract': ['employment', 'employee', 'employer'],
    'Non-Disclosure Agreement (NDA)': ['nda', 'non-disclosure', 'confidentiality'],
    'Court Filing': ['filed', 'filing', 'clerk', 'case no'],
    'Motion': ['motion to', 'motion for'],
    'Complaint': ['complaint', 'plaintiff'],
    'Answer': ['answer to', 'defendant'],
    'Judgment': ['judgment', 'decree'],
    'Order': ['order', 'ordered'],
    'Discovery Request': ['interrogatories', 'request for production', 'request for admission'],
    'Discovery Response': ['response to', 'answers to interrogatories'],
    'Deposition Transcript': ['deposition', 'deponent'],
    'Hearing Transcript': ['hearing', 'proceedings'],
    'Trial Transcript': ['trial', 'jury'],
    'Email': ['from:', 'to:', 'subject:', '@'],
}


class DocumentCategorizer:
    """Automatically categorize documents based on content and filename"""
    
    def __init__(self):
        self.primary_categories = PRIMARY_CATEGORIES
        self.sub_categories = SUB_CATEGORIES
    
    def categorize(
        self, 
        filename: str, 
        content: str, 
        manual_category: Optional[str] = None,
        manual_sub_category: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Categorize a document
        
        Args:
            filename: Document filename
            content: Document text content
            manual_category: Manually specified primary category (overrides auto-detection)
            manual_sub_category: Manually specified sub-category (overrides auto-detection)
        
        Returns:
            Dictionary with category information
        """
        # Use manual category if provided
        if manual_category:
            primary_category = manual_category
            confidence = 1.0
        else:
            # Auto-detect primary category
            primary_category, confidence = self._detect_primary_category(filename, content)
        
        # Use manual sub-category if provided
        if manual_sub_category:
            sub_category = manual_sub_category
            sub_confidence = 1.0
        else:
            # Auto-detect sub-category
            sub_category, sub_confidence = self._detect_sub_category(
                primary_category, filename, content
            )
        
        return {
            'document_type': primary_category,
            'sub_category': sub_category,
            'category_confidence': confidence,
            'sub_category_confidence': sub_confidence,
            'auto_categorized': manual_category is None
        }
    
    def _detect_primary_category(self, filename: str, content: str) -> Tuple[str, float]:
        """Detect primary category from filename and content"""
        text = (filename + " " + content[:5000]).lower()  # Use first 5000 chars
        
        scores = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                scores[category] = score
        
        if not scores:
            return 'legal_document', 0.3  # Default to legal_document with low confidence
        
        # Get category with highest score
        best_category = max(scores, key=scores.get)
        max_score = scores[best_category]
        total_keywords = len(CATEGORY_KEYWORDS[best_category])
        
        # Calculate confidence (0.0 to 1.0)
        confidence = min(max_score / total_keywords, 1.0)
        confidence = max(confidence, 0.5)  # Minimum 0.5 if any keywords match
        
        return best_category, confidence
    
    def _detect_sub_category(
        self, 
        primary_category: str, 
        filename: str, 
        content: str
    ) -> Tuple[Optional[str], float]:
        """Detect sub-category from filename and content"""
        text = (filename + " " + content[:5000]).lower()
        
        # Get possible sub-categories for this primary category
        possible_subs = self.sub_categories.get(primary_category, [])
        
        scores = {}
        for sub_cat in possible_subs:
            keywords = SUB_CATEGORY_KEYWORDS.get(sub_cat, [])
            if keywords:
                score = sum(1 for keyword in keywords if keyword in text)
                if score > 0:
                    scores[sub_cat] = score
        
        if not scores:
            # Return "Other" category with low confidence
            other_cat = f"Other {primary_category.replace('_', ' ').title()}"
            if other_cat not in possible_subs:
                other_cat = possible_subs[-1] if possible_subs else None
            return other_cat, 0.3
        
        # Get sub-category with highest score
        best_sub = max(scores, key=scores.get)
        max_score = scores[best_sub]
        keywords_count = len(SUB_CATEGORY_KEYWORDS.get(best_sub, []))
        
        # Calculate confidence
        confidence = min(max_score / max(keywords_count, 1), 1.0)
        confidence = max(confidence, 0.5)
        
        return best_sub, confidence
    
    def get_categories_for_display(self) -> Dict[str, list]:
        """Get all categories formatted for display/selection"""
        return {
            category: {
                'name': name,
                'sub_categories': self.sub_categories.get(category, [])
            }
            for category, name in self.primary_categories.items()
        }
    
    def validate_category(self, primary: str, sub: Optional[str] = None) -> bool:
        """Validate that category and sub-category are valid"""
        if primary not in self.primary_categories:
            return False
        
        if sub and primary in self.sub_categories:
            return sub in self.sub_categories[primary]
        
        return True


# Example usage
if __name__ == "__main__":
    categorizer = DocumentCategorizer()
    
    # Test with sample documents
    test_cases = [
        {
            'filename': 'Operating_Agreement_LLC.pdf',
            'content': 'This Operating Agreement is entered into by and between the members of...'
        },
        {
            'filename': 'Motion_to_Dismiss.pdf',
            'content': 'MOTION TO DISMISS. Plaintiff respectfully moves this Court to dismiss...'
        },
        {
            'filename': 'Deposition_Transcript_Smith.pdf',
            'content': 'DEPOSITION OF JOHN SMITH. Q: Please state your name. A: John Smith...'
        },
        {
            'filename': 'Email_from_Attorney.pdf',
            'content': 'From: attorney@law.com To: client@email.com Subject: Case Update...'
        }
    ]
    
    print("Document Categorization Test\n" + "="*60)
    for i, test in enumerate(test_cases, 1):
        result = categorizer.categorize(test['filename'], test['content'])
        print(f"\n{i}. {test['filename']}")
        print(f"   Primary: {result['document_type']} (confidence: {result['category_confidence']:.2f})")
        print(f"   Sub: {result['sub_category']} (confidence: {result['sub_category_confidence']:.2f})")
    
    print("\n" + "="*60)
    print("\nAvailable Categories:")
    for category, info in categorizer.get_categories_for_display().items():
        print(f"\n{category}: {info['name']}")
        for sub in info['sub_categories']:
            print(f"  - {sub}")
