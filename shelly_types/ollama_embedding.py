from langchain.embeddings.base import Embeddings
import requests
from typing import List

class OllamaEmbedding(Embeddings):
    def __init__(self, model_name: str = "llama2"):
        self.model_name = model_name
        self.url = "http://localhost:11434/api/embeddings"

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed documents using Ollama API"""
        embeddings = []
        for text in texts:
            response = requests.post(
                self.url,
                json={"model": self.model_name, "prompt": text}
            )
            embedding = response.json()["embedding"]
            embeddings.append(embedding)
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed a query using Ollama API"""
        response = requests.post(
            self.url,
            json={"model": self.model_name, "prompt": text}
        )
        return response.json()["embedding"]
