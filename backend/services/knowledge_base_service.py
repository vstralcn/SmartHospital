from __future__ import annotations

import json
import math
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "medical_knowledge.json"
_EMBED_DIM = 384
_TOKEN_RE = re.compile(r"[a-zA-Z]+|[0-9]+|[\u4e00-\u9fff]")


def _tokenize(text: str) -> List[str]:
    """Tokenize mixed CJK / ASCII text into characters and bigrams.

    Chinese has no whitespace word boundaries, so we index single Han
    characters plus adjacent-character bigrams. ASCII runs (drug names, ICD
    codes) are kept whole. This gives the local embedding enough overlap signal
    for meaningful cosine similarity without any external tokenizer.
    """

    units = _TOKEN_RE.findall(text.lower())
    tokens = list(units)
    for first, second in zip(units, units[1:]):
        tokens.append(first + second)
    return tokens


class LocalEmbeddings(Embeddings):
    """Deterministic, dependency-free embedding for offline RAG.

    Each token is hashed into a fixed-dimension bag-of-features vector (term
    frequency), then L2-normalised so that :class:`InMemoryVectorStore` cosine
    similarity behaves like a TF retriever. It needs no API key or model
    download, so the KnowledgeAgent works under the Mock provider too, while
    still exercising the genuine LangChain ``Embeddings`` + vector-store
    retrieval pipeline.
    """

    def __init__(self, dim: int = _EMBED_DIM) -> None:
        self.dim = dim

    def _embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        for token in _tokenize(text):
            idx = hash(token) % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)


class KnowledgeBaseService:
    """RAG knowledge base over a curated medical corpus.

    Documents are chunked with ``RecursiveCharacterTextSplitter`` and indexed
    in a LangChain ``InMemoryVectorStore`` using :class:`LocalEmbeddings`. The
    KnowledgeAgent queries :meth:`search` to ground diagnosis output in
    citable references.
    """

    def __init__(self, data_file: Path = _DATA_FILE) -> None:
        self.data_file = data_file
        self.embeddings = LocalEmbeddings()
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=240, chunk_overlap=40, separators=["\n\n", "\n", "。", "；", " ", ""]
        )
        self.store: Optional[InMemoryVectorStore] = None
        self._doc_count = 0
        self._build()

    def _load_entries(self) -> List[Dict[str, Any]]:
        try:
            with open(self.data_file, encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, list) else []
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to load knowledge base from {self.data_file}: {exc}")
            return []

    def _build(self) -> None:
        documents: List[Document] = []
        for entry in self._load_entries():
            body = str(entry.get("content", "")).strip()
            if not body:
                continue
            metadata = {
                "id": entry.get("id", ""),
                "title": entry.get("title", ""),
                "disease": entry.get("disease", ""),
                "source": entry.get("source", ""),
            }
            for chunk in self.splitter.split_text(body):
                documents.append(Document(page_content=chunk, metadata=dict(metadata)))

        self._doc_count = len(documents)
        if documents:
            self.store = InMemoryVectorStore.from_documents(documents, self.embeddings)
        logger.info(
            f"KnowledgeBaseService indexed {self._doc_count} chunks "
            f"from {self.data_file.name}"
        )

    @property
    def size(self) -> int:
        return self._doc_count

    def search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """Return the top-k most relevant knowledge chunks for ``query``."""

        if self.store is None or not query.strip():
            return []
        results = self.store.similarity_search_with_score(query, k=k)
        references: List[Dict[str, Any]] = []
        for doc, score in results:
            references.append(
                {
                    "title": doc.metadata.get("title", ""),
                    "disease": doc.metadata.get("disease", ""),
                    "source": doc.metadata.get("source", ""),
                    "snippet": doc.page_content,
                    "score": round(float(score), 4),
                }
            )
        return references


_INSTANCE: Optional[KnowledgeBaseService] = None
_LOCK = threading.Lock()


def get_knowledge_base() -> KnowledgeBaseService:
    """Process-wide singleton so the corpus is indexed only once."""

    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = KnowledgeBaseService()
    return _INSTANCE
