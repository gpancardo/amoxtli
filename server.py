#!/usr/bin/env python3
# Amoxtli - Mexican Law Knowledge Graph Server
# Flask backend: semantic search + DeepSeek chat (graph-grounded) + graph data + topics
import json, os, pickle, re
import numpy as np
import requests
from flask import Flask, request, jsonify, send_from_directory
import corpus

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'datos', 'Separado')
WEB = os.path.join(ROOT, 'web')

try:
    from dotenv import load_dotenv; load_dotenv(os.path.join(ROOT, '.env'))
except ImportError:
    pass
DEEPSEEK_KEY = os.environ.get('DS_TOKEN') or os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_URL = 'https://api.deepseek.com/chat/completions'
DEEPSEEK_MODEL = os.environ.get('DS_MODEL', 'deepseek-v4-flash')  # flash tier; -pro is pricier

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

# --- Load graph data ---
with open(os.path.join(WEB, 'graph.json'), 'r') as f:
    full_graph = json.load(f)

with open(os.path.join(WEB, 'laws_index.json'), 'r') as f:
    laws_index = json.load(f)

try:
    with open(os.path.join(WEB, 'clusters.json'), 'r') as f:
        clusters_data = json.load(f)
except FileNotFoundError:
    clusters_data = {'clusters': {}}

law_map = {l['name']: l for l in laws_index}

# --- Full raw text per law (from datos/TextoPlano, via corpus.py) ---
print("Loading raw law texts...")
law_texts = corpus.load()                       # {law_name: full_text}
text_by_norm = {corpus.norm(n): (n, t) for n, t in law_texts.items()}

def find_text(name):
    """Best-effort match a (mojibake-fixed) law name to its raw full text."""
    key = corpus.norm(name)
    if key in text_by_norm:
        return text_by_norm[key]
    for nk, pair in text_by_norm.items():        # prefix fallback, like corpus.load
        if nk.startswith(key[:30]) or key.startswith(nk[:30]):
            return pair
    return None

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
    """Retrieve relevant law text (for content questions) + knowledge-graph relations."""
    q_emb = model.encode([msg])
    faiss.normalize_L2(q_emb)
    scores, ids = faiss_index.search(q_emb, 12)   # more, longer passages → answer on content
    passages, laws = [], []
    for score, idx in zip(scores[0], ids[0]):
        if score < 0.3:
            continue
        chunk = chunks[idx]
        law = chunk['law']
        passages.append(f"[{fix_moji(law)}] {fix_moji(chunk['text'][:900])}")
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
    fixed_laws = [fix_moji(l) for l in laws]
    return ('\n\n'.join(passages) or 'Sin pasajes relevantes.',
            '\n'.join(relations) or 'Sin relaciones.', fixed_laws)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    msg = data.get('message', '').strip()
    history = data.get('history', [])[-6:]  # last few turns for continuity
    if not msg:
        return jsonify({'response': ''})
    if not DEEPSEEK_KEY:
        return jsonify({'response': 'Falta la variable de entorno DEEPSEEK_API_KEY en el servidor.'}), 503
    passages, relations, ctx_laws = graph_context(msg)
    system = (
        "Eres Tlamatini, un asistente de consulta sobre legislación mexicana. Respondes "
        "sobre el CONTENIDO de las leyes usando los pasajes de su texto, y sobre sus "
        "relaciones usando el grafo. Explica lo que dicen las leyes, cita el nombre de la "
        "ley y el artículo cuando aparezca en los pasajes. No inventes artículos ni datos "
        "fuera del contexto; si el texto no alcanza, dilo. Ofreces información general, no "
        "asesoría legal.\n\n"
        f"Texto de las leyes (pasajes):\n{passages}\n\nRelaciones del grafo:\n{relations}"
    )
    messages = [{'role': 'system', 'content': system}]
    for h in history:
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({'role': h['role'], 'content': h['content']})
    messages.append({'role': 'user', 'content': msg})
    try:
        r = requests.post(DEEPSEEK_URL, timeout=60,
            headers={'Authorization': f'Bearer {DEEPSEEK_KEY}'},
            json={'model': DEEPSEEK_MODEL, 'messages': messages, 'temperature': 0.3})
        r.raise_for_status()
        reply = r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        reply = f'No pude consultar el modelo remoto: {e}'
    return jsonify({'response': reply, 'laws': ctx_laws})

# --- Graph ---
@app.route('/api/graph')
def graph():
    return jsonify(full_graph)

@app.route('/api/clusters')
def clusters():
    # Legend only: id → label/color/size (drop the heavy 'laws'/'coords' payload).
    legend = {cid: {'label': c['label'], 'color': c['color'], 'size': c['size'],
                    'terms': c.get('terms', [])}
              for cid, c in clusters_data.get('clusters', {}).items()}
    return jsonify(legend)

@app.route('/api/graph/map')
def graph_map():
    """Flat Obsidian-style map: every law as a node (colored by semantic branch,
    seeded at its UMAP position) + the law→law citation edges. No institutions,
    no drill-down — one living canvas."""
    law_nodes = [n for n in full_graph['nodes'] if n.get('group') == 'law']
    law_ids = set(n['id'] for n in law_nodes)
    edges = [e for e in full_graph['edges']
             if e.get('label') == 'referencia' and e['from'] in law_ids and e['to'] in law_ids]
    return jsonify({'nodes': law_nodes, 'edges': edges})

@app.route('/api/law/<path:name>')
def law_detail(name):
    law = law_map.get(name)
    if not law:
        return jsonify({'error': 'not found'}), 404
    return jsonify(law)

@app.route('/api/text/<path:name>')
def law_text(name):
    hit = find_text(name)
    if not hit:
        return jsonify({'error': 'not found', 'name': name}), 404
    real_name, text = hit
    return jsonify({'name': real_name, 'text': text})

@app.route('/')
def index():
    return send_from_directory(WEB, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(WEB, path)

if __name__ == '__main__':
    print("Amoxtli server at http://localhost:8765")
    app.run(host='0.0.0.0', port=8765)
