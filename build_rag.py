#!/usr/bin/env python3
"""
Build FAISS search index from law texts + serve Flask app.
"""
import json, os, re, hashlib, pickle
import numpy as np
import corpus

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'datos', 'Separado')
OUT = os.path.join(ROOT, 'web')

# Chunk law texts into searchable pieces
def chunk_text(text, name, chunk_size=500, overlap=50):
    """Split law text into overlapping chunks."""
    if not text:
        return []
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        if len(chunk_words) < 10:
            continue
        chunk_text = ' '.join(chunk_words)
        chunk_id = hashlib.md5(f'{name}_{i}'.encode()).hexdigest()[:12]
        chunks.append({
            'id': chunk_id,
            'law': name,
            'text': chunk_text[:2000],  # cap at 2000 chars
            'offset': i,
        })
    return chunks

def build_index():
    from sentence_transformers import SentenceTransformer
    import faiss
    
    print("Loading embedding model...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')  # Spanish-aware
    
    laws = corpus.load()                       # name -> real full text
    all_chunks = []
    print(f"Chunking {len(laws)} laws...")
    for name, content in laws.items():
        all_chunks.extend(chunk_text(content, name))
    print(f"Total chunks: {len(all_chunks)}")
    
    # Generate embeddings
    texts = [c['text'] for c in all_chunks]
    print("Generating embeddings (this may take a few minutes)...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)
    
    # Build FAISS index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    
    # Save
    faiss.write_index(index, os.path.join(OUT, 'search.index'))
    with open(os.path.join(OUT, 'chunks.pkl'), 'wb') as f:
        pickle.dump(all_chunks, f)
    
    print(f"Index saved: {index.ntotal} vectors, {dim} dims")
    return True

if __name__ == '__main__':
    build_index()
