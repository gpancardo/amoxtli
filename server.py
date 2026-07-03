#!/usr/bin/env python3
# AmoxtliLex - Mexican Law Knowledge Graph Server
# Flask backend: semantic search + DeepSeek chat (graph-grounded) + graph data + topics
import json, os, pickle, re
import numpy as np
import requests
from flask import Flask, request, jsonify, send_from_directory

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'datos', 'Separado')
WEB = os.path.join(ROOT, 'web')

DEEPSEEK_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_URL = 'https://api.deepseek.com/chat/completions'

def fix_moji(s):
    # ponytail: source text is double-encoded UTF-8; latin1 roundtrip repairs it, keep original on failure
    try:
        r = s.encode('latin1').decode('utf-8')
        return r if '�' not in r else s
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s

app = Flask(__name__, static_folder=WEB)

# --- Load search index ---
print("Loading search index...")
import faiss
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')  # Spanish-aware
faiss_index = faiss.read_index(os.path.join(WEB, 'search.index'))
with open(os.path.join(WEB, 'chunks.pkl'), 'rb') as f:
    chunks = pickle.load(f)

# --- Load multi-level graph data ---
with open(os.path.join(WEB, 'graph_multi.json'), 'r') as f:
    multi_graph = json.load(f)

with open(os.path.join(WEB, 'graph_levels.json'), 'r') as f:
    graph_levels = json.load(f)

with open(os.path.join(WEB, 'graph.json'), 'r') as f:
    full_graph = json.load(f)

with open(os.path.join(WEB, 'laws_index.json'), 'r') as f:
    laws_index = json.load(f)

law_map = {l['name']: l for l in laws_index}

# --- Load topics ---
try:
    with open(os.path.join(WEB, 'topics.json'), 'r') as f:
        topics_data = json.load(f)
except:
    topics_data = {'continents': {}, 'law_topics': {}, 'topic_labels': {}}

# --- Search ---
@app.route('/api/search')
def search():
    # Semantic search over law chunks. Returns the full ranked list; the client paginates.
    q = request.args.get('q', '').strip()
    top_k = min(int(request.args.get('k', 40)), 60)
    if not q:
        return jsonify({'results': []})
    q_emb = model.encode([q])
    faiss.normalize_L2(q_emb)
    scores, ids = faiss_index.search(q_emb, top_k)
    results = []
    for score, idx in zip(scores[0], ids[0]):
        if score < 0.3:
            continue
        chunk = chunks[idx]
        results.append({
            'law': fix_moji(chunk['law']),
            'text': fix_moji(chunk['text'][:300]),
            'score': round(float(score), 3),
        })
    return jsonify({'results': results})

# --- Chat (graph-grounded, DeepSeek) ---
def graph_context(msg):
    """Retrieve relevant law chunks and expand them into knowledge-graph relations."""
    q_emb = model.encode([msg])
    faiss.normalize_L2(q_emb)
    scores, ids = faiss_index.search(q_emb, 6)
    passages, laws = [], []
    for score, idx in zip(scores[0], ids[0]):
        if score < 0.3:
            continue
        chunk = chunks[idx]
        law = chunk['law']
        passages.append(f"[{fix_moji(law)}] {fix_moji(chunk['text'][:500])}")
        if law not in laws:
            laws.append(law)
    # Expand each law into its knowledge-graph neighborhood: materia, cited laws, institutions
    relations = []
    for law in laws[:4]:
        meta = law_map.get(law, {}) or {}
        refs = meta.get('references', [])[:8]
        inst = meta.get('institutions', [])[:8]
        abro = meta.get('abrogates', [])[:4]
        parts = [f"- {fix_moji(law)} (materia: {meta.get('materia', '—')})"]
        if abro:
            parts.append(f"  · abroga/reemplaza a: {', '.join(fix_moji(a) for a in abro)}")
        if refs:
            parts.append(f"  · cita las leyes: {', '.join(fix_moji(r) for r in refs)}")
        if inst:
            parts.append(f"  · involucra a: {', '.join(fix_moji(i) for i in inst)}")
        relations.append('\n'.join(parts))
    return '\n\n'.join(passages) or 'Sin pasajes relevantes.', '\n'.join(relations) or 'Sin relaciones.'

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    msg = data.get('message', '').strip()
    history = data.get('history', [])[-6:]  # last few turns for continuity
    if not msg:
        return jsonify({'response': ''})
    if not DEEPSEEK_KEY:
        return jsonify({'response': 'Falta la variable de entorno DEEPSEEK_API_KEY en el servidor.'}), 503
    passages, relations = graph_context(msg)
    system = (
        "Eres un asistente experto en legislación mexicana. Respondes con base en el "
        "grafo de conocimiento y los pasajes proporcionados. Sé claro y preciso, cita las "
        "leyes por su nombre y no inventes artículos ni datos fuera del contexto.\n\n"
        f"Relaciones del grafo:\n{relations}\n\nPasajes:\n{passages}"
    )
    messages = [{'role': 'system', 'content': system}]
    for h in history:
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({'role': h['role'], 'content': h['content']})
    messages.append({'role': 'user', 'content': msg})
    try:
        r = requests.post(DEEPSEEK_URL, timeout=60,
            headers={'Authorization': f'Bearer {DEEPSEEK_KEY}'},
            json={'model': 'deepseek-chat', 'messages': messages, 'temperature': 0.3})
        r.raise_for_status()
        reply = r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        reply = f'No pude consultar el modelo remoto: {e}'
    return jsonify({'response': reply})

# --- Graph ---
@app.route('/api/graph')
def graph():
    return jsonify(full_graph)

@app.route('/api/graph/level0')
def graph_level0():
    return jsonify(multi_graph.get('level0', {'nodes': [], 'edges': []}))

@app.route('/api/graph/continent/<path:cid>')
def graph_continent(cid):
    """A clean materia view: the continent's laws + the institutions they name,
    plus citation edges *between* laws in this materia. Cross-materia citations
    live in the law info panel, not here — keeps the graph readable."""
    laws = graph_levels.get('continents', {}).get(cid, [])
    law_ids = set(l['id'] for l in laws)

    # institutions (org nodes) touched by these laws
    inst_ids = set()
    for e in full_graph['edges']:
        if e.get('label') == 'regula':
            if e['from'] in law_ids:
                inst_ids.add(e['to'])
    institutions = [n for n in full_graph['nodes'] if n['id'] in inst_ids]

    edges = []
    for e in full_graph['edges']:
        if e.get('label') == 'regula' and e['from'] in law_ids and e['to'] in inst_ids:
            edges.append(e)
        elif e.get('label') == 'referencia' and e['from'] in law_ids and e['to'] in law_ids:
            edges.append(e)

    return jsonify({'nodes': laws + institutions, 'edges': edges})

@app.route('/api/topics')
def topics():
    return jsonify(topics_data)

@app.route('/api/law/<path:name>')
def law_detail(name):
    law = law_map.get(name)
    if not law:
        return jsonify({'error': 'not found'}), 404
    return jsonify(law)

@app.route('/')
def index():
    return send_from_directory(WEB, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(WEB, path)

if __name__ == '__main__':
    print("AmoxtliLex server at http://localhost:8765")
    app.run(host='0.0.0.0', port=8765)
