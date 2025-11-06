#!/usr/bin/env python3
"""
Extract text from various document formats
"""

import os
import PyPDF2
import docx
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

class TextExtractor:
    """Extract text from PDF, DOCX, and TXT files, with OCR for scanned PDFs"""

    def extract(self, file_path):
        """Extract text from a file, using OCR if necessary"""
        file_extension = os.path.splitext(file_path)[1].lower()

        if file_extension == ".pdf":
            return self._extract_from_pdf(file_path)
        elif file_extension == ".docx":
            return self._extract_from_docx(file_path)
        elif file_extension == ".txt":
            return self._extract_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

    def _extract_from_pdf(self, file_path):
        """Extract text from a PDF, using OCR as a fallback"""
        text = ""
        try:
            with open(file_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text

            # If text is minimal, it might be a scanned PDF
            if len(text.strip()) < 100:
                print("PDF appears to be scanned, falling back to OCR...")
                return self._ocr_pdf(file_path)
            
            return text
        except Exception as e:
            print(f"Error extracting text from PDF, falling back to OCR: {e}")
            return self._ocr_pdf(file_path)

    def _extract_from_docx(self, file_path):
        """Extract text from a DOCX file"""
        text = ""
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text

    def _extract_from_txt(self, file_path):
        """Extract text from a TXT file"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _ocr_pdf(self, file_path):
        """Use OCR to extract text from a scanned PDF"""
        text = ""
        try:
            images = convert_from_path(file_path)
            for i, image in enumerate(images):
                print(f"  OCR processing page {i+1}/{len(images)}...")
                text += pytesseract.image_to_string(image)
            return text
        except Exception as e:
            print(f"OCR failed for {file_path}: {e}")
            return ""

if __name__ == "__main__":
    # Example usage
    extractor = TextExtractor()
    
    # Create dummy files for testing
    if not os.path.exists("test_docs"):
        os.makedirs("test_docs")
    
    with open("test_docs/test.txt", "w") as f:
        f.write("This is a test text file.")
        
    # You would need to add a test.docx and test.pdf to the test_docs folder
    # For now, we just test the txt extractor
    
    try:
        text = extractor.extract("test_docs/test.txt")
        print("\n--- Extracted from TXT ---")
        print(text)
    except Exception as e:
        print(f"Error testing TXT: {e}")
