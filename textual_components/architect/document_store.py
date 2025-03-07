import requests
from bs4 import BeautifulSoup
import chromadb
from chromadb.config import Settings
from typing import List, Dict
import hashlib

class DocumentStore:
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            is_persistent=True
        ))
        self.collection = self.client.get_or_create_collection("documentation")

    async def add_url_content(self, url: str) -> None:
        """Scrape URL content and add to ChromaDB."""
        try:
            # Fetch and parse content
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract text content (customize based on your needs)
            content = soup.get_text()
            
            # Create chunks (simple implementation - you might want to use a more sophisticated approach)
            chunks = self._chunk_text(content, chunk_size=1000)
            
            # Generate IDs for chunks
            ids = [hashlib.md5(f"{url}_{i}".encode()).hexdigest() 
                  for i in range(len(chunks))]
            
            # Add to ChromaDB
            self.collection.add(
                documents=chunks,
                ids=ids,
                metadatas=[{"source": url} for _ in chunks]
            )
            
            return True
        except Exception as e:
            raise Exception(f"Failed to process URL: {str(e)}")

    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """Split text into chunks of approximately equal size."""
        words = text.split()
        chunks = []
        current_chunk = []
        current_size = 0
        
        for word in words:
            current_size += len(word) + 1  # +1 for space
            if current_size > chunk_size:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_size = len(word)
            else:
                current_chunk.append(word)
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks

    def query_documents(self, query: str, n_results: int = 5) -> List[Dict]:
        """Query the document store."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results
