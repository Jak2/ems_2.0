# Vector Database in EMS 2.0 - FAISS Implementation

A guide to the vector database used in this project for RAG (Retrieval-Augmented Generation).

---

## What's Installed

| Component | Purpose | Installation |
|-----------|---------|--------------|
| **FAISS** | Vector similarity search | `pip install faiss-cpu` |
| **Sentence-Transformers** | Generate embeddings | `pip install sentence-transformers` |

## File Locations

| File | Purpose |
|------|---------|
| `backend/app/services/vectorstore_faiss.py` | FAISS wrapper implementation |
| `backend/app/services/embeddings.py` | Sentence-transformers wrapper |
| `backend/data/faiss/index.faiss` | Persisted vector index |
| `backend/data/faiss/meta.json` | Metadata (text + employee mapping) |

---

## How It Works

# 1. Embedding generation (384 dimensions)
from app.services.embeddings import Embeddings
emb = Embeddings()  # Uses all-MiniLM-L6-v2

# 2. FAISS index (cosine similarity via normalized inner product)
self.index = faiss.IndexFlatIP(dim)  # 384-dim vectors

# 3. Add chunks with employee association
def add_chunks(self, employee_id: int, chunks: List[str]):
    vecs = self.emb.embed_texts(chunks)  # Text → 384-dim vectors
    self.index.add(vecs)
    # Store metadata: {id, employee_id, text}

# 4. Semantic search
def search(self, query: str, top_k: int = 5):
    qvec = self.emb.embed_texts([query])
    D, I = self.index.search(qvec, top_k)  # Returns distances & indices
    return results  # [{text, employee_id, score}, ...]

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAG PIPELINE                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INDEXING (at CV upload time)                                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│  │  Resume  │───▶│  Chunk   │───▶│  Embed   │───▶│  FAISS   │ │
│  │   Text   │    │ (500char)│    │ (384-dim)│    │  Index   │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│                                                                  │
│  RETRIEVAL (at query time)                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│  │  User    │───▶│  Embed   │───▶│  Search  │───▶│  Top-K   │ │
│  │  Query   │    │  Query   │    │  FAISS   │    │  Chunks  │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Code Implementation

📄 **File:** `backend/app/services/vectorstore_faiss.py`

```python
import faiss
import numpy as np
from app.services.embeddings import Embeddings

class FaissVectorStore:
    """FAISS vector store with disk persistence."""

    def __init__(self, path: str):
        self.path = path
        self.index_path = os.path.join(path, "index.faiss")
        self.meta_path = os.path.join(path, "meta.json")
        self.emb = Embeddings()  # Sentence-transformers
        self._load()

    def _load(self):
        """Load existing index from disk."""
        self.meta: List[Dict] = []
        if os.path.exists(self.meta_path):
            with open(self.meta_path, "r") as f:
                self.meta = json.load(f)
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
        else:
            self.index = None

    def add_chunks(self, employee_id: int, chunks: List[str]):
        """Add text chunks to the index."""
        if not chunks:
            return []

        # 1. Generate embeddings (text → 384-dim vectors)
        vecs = self.emb.embed_texts(chunks)
        n, dim = vecs.shape

        # 2. Create index if first time
        if self.index is None:
            # IndexFlatIP = Inner Product (cosine similarity on normalized vectors)
            self.index = faiss.IndexFlatIP(dim)

        # 3. Add vectors to index
        start_id = len(self.meta)
        self.index.add(vecs)

        # 4. Store metadata (maps vector ID → employee + text)
        for i, txt in enumerate(chunks):
            self.meta.append({
                "id": start_id + i,
                "employee_id": employee_id,
                "text": txt
            })

        # 5. Persist to disk
        self._save_meta()
        self._save_index()

        return list(range(start_id, start_id + n))

    def search(self, query: str, top_k: int = 5, employee_id: Optional[int] = None):
        """Semantic search with optional employee filter."""
        if self.index is None or len(self.meta) == 0:
            return []

        # 1. Embed the query
        qvec = self.emb.embed_texts([query])

        # 2. Search FAISS index
        D, I = self.index.search(qvec, min(top_k * 5, len(self.meta)))
        # D = distances (similarity scores)
        # I = indices of matching vectors

        # 3. Build results with optional filtering
        results = []
        for score, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            m = self.meta[idx].copy()
            m["score"] = float(score)

            # Optional: filter by employee
            if employee_id is None or m.get("employee_id") == employee_id:
                results.append(m)

            if len(results) >= top_k:
                break

        return results

    def _save_meta(self):
        with open(self.meta_path, "w") as f:
            json.dump(self.meta, f)

    def _save_index(self):
        if self.index is not None:
            faiss.write_index(self.index, self.index_path)
```

---

## Key Technical Details

### Embedding Model

| Property | Value |
|----------|-------|
| **Model** | `all-MiniLM-L6-v2` |
| **Dimensions** | 384 |
| **Type** | Sentence-transformers |
| **Speed** | Fast (optimized for CPU) |
| **Quality** | Good for semantic similarity |

### FAISS Index Type

```python
self.index = faiss.IndexFlatIP(dim)  # Inner Product
```

| Index Type | Description | Use Case |
|------------|-------------|----------|
| `IndexFlatIP` | Inner Product (exact search) | Small datasets, cosine similarity |
| `IndexFlatL2` | L2/Euclidean distance | When direction doesn't matter |
| `IndexIVFFlat` | Inverted file (approximate) | Large datasets, faster search |
| `IndexHNSW` | Graph-based (approximate) | Very large datasets |

**Why `IndexFlatIP`?** For normalized vectors, inner product = cosine similarity. Exact search is fine for our scale (thousands of chunks, not millions).

### Chunking Strategy

```python
# In main.py during CV processing
CHUNK_SIZE = 500       # Characters per chunk
CHUNK_OVERLAP = 100    # Overlap between chunks

def chunk_text(text: str) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP  # Overlap for context continuity
    return chunks
```

**Why overlap?** Ensures information spanning chunk boundaries isn't lost.

---

## Usage in the Project

### At Upload Time (Indexing)

```python
# backend/app/main.py - process_cv_background()

# 1. Extract text from PDF
pdf_text = extract_text_from_bytes(contents)

# 2. Chunk the text
chunks = chunk_text(pdf_text)

# 3. Add to FAISS index
vectorstore.add_chunks(employee.id, chunks)
```

### At Query Time (Retrieval)

```python
# backend/app/main.py - chat endpoint

# 1. Search for relevant chunks
results = vectorstore.search(
    query=user_prompt,
    top_k=5,
    employee_id=employee.id  # Filter to specific employee
)

# 2. Build context from retrieved chunks
retrieved_text = "\n".join([r["text"] for r in results])

# 3. Include in LLM prompt
prompt = f"""
Context from resume:
{retrieved_text}

Question: {user_prompt}
"""
```

---

## FAISS vs Other Vector Databases

| Feature | FAISS | Pinecone | Milvus | Chroma |
|---------|-------|----------|--------|--------|
| **Type** | Library | Managed Service | Self-hosted | Library |
| **Server Required** | No | Yes (cloud) | Yes | No |
| **Persistence** | File-based | Cloud | Database | File-based |
| **Scale** | Millions | Billions | Billions | Millions |
| **Cost** | Free | Pay-per-use | Free (self-host) | Free |
| **Best For** | PoC, on-premise | Production SaaS | Enterprise | Prototyping |

### Why FAISS for This Project?

1. **On-premise requirement** - No external API calls
2. **Simplicity** - No server to manage
3. **Sufficient scale** - Handles thousands of employees
4. **Disk persistence** - Survives restarts
5. **Zero cost** - Open source

---

## Interview Questions & Answers

### Q: What is FAISS?

> "FAISS is Facebook AI Similarity Search - an open-source library for efficient similarity search on dense vectors. It's not a database but a library that provides various index types for approximate nearest neighbor search. In our project, we use `IndexFlatIP` for exact cosine similarity search with disk persistence."

### Q: Why not use Pinecone or a managed service?

> "This project is designed for on-premise deployment where data privacy is critical. Resume data shouldn't leave the organization's infrastructure. FAISS runs entirely in-process with no external dependencies. For production scale with millions of vectors, we'd consider Milvus (self-hosted) or Pinecone (if cloud is acceptable)."

### Q: How do you handle similarity search?

> "We use inner product similarity on normalized vectors, which is equivalent to cosine similarity. The embedding model (all-MiniLM-L6-v2) produces 384-dimensional vectors. At query time, we embed the user's question and find the top-k most similar chunks from the resume. These chunks are then included in the LLM prompt for grounded responses."

### Q: What's the chunking strategy?

> "We use 500-character chunks with 100-character overlap. The overlap ensures that information spanning chunk boundaries isn't lost during retrieval. For example, if a skill description starts at the end of one chunk, the overlap ensures it's also captured in the next chunk."

### Q: How does this prevent hallucination?

> "RAG grounds the LLM's responses in actual document content. Instead of relying on the LLM's training data (which might be outdated or wrong), we retrieve specific relevant passages from the employee's resume and include them in the prompt. The LLM is instructed to ONLY use information from these retrieved passages."

---

## Metadata Structure

📄 **File:** `data/faiss/meta.json`

```json
[
  {
    "id": 0,
    "employee_id": 1,
    "text": "John Doe is a software engineer with 5 years of experience..."
  },
  {
    "id": 1,
    "employee_id": 1,
    "text": "...experience in Python, JavaScript, and cloud technologies..."
  },
  {
    "id": 2,
    "employee_id": 2,
    "text": "Sarah Smith graduated from MIT with a degree in Computer Science..."
  }
]
```

Each entry maps a vector ID to:
- `employee_id` - Which employee this chunk belongs to
- `text` - The original text (for retrieval and display)

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| **Embedding time** | ~50ms per chunk |
| **Index search** | <100ms for top-5 |
| **Index size** | ~1.5KB per chunk (384 × 4 bytes) |
| **Metadata size** | ~500 bytes per chunk |

For 1000 employees × 10 chunks each = 10,000 vectors:
- Index size: ~15MB
- Metadata: ~5MB
- Search time: <100ms

---

*Last updated: February 3, 2026*
