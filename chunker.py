#!/usr/bin/env python3
"""
Chunk text into smaller pieces for embedding
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken

class Chunker:
    """Chunk text using a recursive character splitter"""

    def __init__(self, chunk_size=300, chunk_overlap=75):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.encoding_for_model("gpt-4")
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=lambda t: len(self.encoding.encode(t)),
            separators=["\n\n", "\n", ". ", " ", ""],
            keep_separator=True
        )

    def chunk(self, text, metadata):
        """Chunk text and enrich with metadata"""
        chunks = self.splitter.split_text(text)
        enriched_chunks = []
        char_position = 0

        for i, chunk_text in enumerate(chunks):
            enriched_chunks.append({
                "chunk_index": i,
                "chunk_text": chunk_text,
                "token_count": len(self.encoding.encode(chunk_text)),
                "start_char": char_position,
                "end_char": char_position + len(chunk_text),
                "metadata": {
                    **metadata,
                    "chunk_id": f"{metadata['document_id']}_chunk_{i}"
                }
            })
            char_position += len(chunk_text) - self.chunk_overlap

        return enriched_chunks

if __name__ == "__main__":
    # Example usage
    chunker = Chunker()
    
    sample_text = """
    This is a long document. It has multiple paragraphs.
    Each paragraph should be chunked appropriately.
    The chunker will split the text into smaller pieces.
    This is important for creating accurate embeddings.
    """
    
    metadata = {'document_id': 'doc123', 'filename': 'sample.txt'}
    
    chunks = chunker.chunk(sample_text, metadata)
    
    print("--- Chunked Text ---")
    for chunk in chunks:
        print(f"Chunk {chunk['chunk_index']}:")
        print(f"  Text: {chunk['chunk_text'][:50]}...")
        print(f"  Tokens: {chunk['token_count']}")
        print(f"  Metadata: {chunk['metadata']}")
