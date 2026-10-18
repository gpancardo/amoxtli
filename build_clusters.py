#!/usr/bin/env python3
"""
Ramas semánticas por embeddings (reemplaza la clasificación por keywords).

Promedia los vectores de los chunks de cada ley (del índice FAISS), reduce con
UMAP y agrupa con HDBSCAN — clusters "naturales", no categorías duras. Cada
cluster se nombra con DeepSeek a partir de sus leyes (fallback: términos c-TF-IDF).
También guarda coordenadas UMAP 2D por ley para sembrar el layout tipo Obsidian.

Salida: web/clusters.json
  { "law_clusters": {ley: cid}, "clusters": {cid: {label,color,size,terms,laws}},
    "coords": {ley: [x,y]} }

Pipeline: build_topics.py → build_clusters.py → build_kg.py
"""
import json, os, re, colorsys
import numpy as np
import faiss, pickle
import umap, hdbscan
from collections import defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, 'web')
try:
    from dotenv import load_dotenv; load_dotenv(os.path.join(ROOT, '.env'))
except ImportError:
    pass
DEEPSEEK_KEY = os.environ.get('DS_TOKEN') or os.environ.get('DEEPSEEK_API_KEY', '')

def fix_moji(s):
    try:
        r = s.encode('latin1').decode('utf-8')
        return r if '�' not in r else s
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s

STOP = set("de la el los las en y a por para del con una uno que se su sus al o "
           "materia general federal ley leyes nacional nacionales estados unidos "
           "mexicanos mexicana república reglamentaria artículo público pública "
           "sobre e u organización orgánica".split())

def law_vectors():
    """{law_name: unit mean-vector} from the FAISS chunk index."""
    idx = faiss.read_index(os.path.join(WEB, 'search.index'))
    chunks = pickle.load(open(os.path.join(WEB, 'chunks.pkl'), 'rb'))
    by_law = defaultdict(list)
    for i, c in enumerate(chunks):
        by_law[fix_moji(c['law'])].append(i)
    names, mats = [], []
    for law, ids in by_law.items():
        v = np.mean([idx.reconstruct(i) for i in ids], axis=0)
        n = np.linalg.norm(v)
        if n:
            names.append(law); mats.append(v / n)
    return names, np.array(mats, dtype='float32')

def palette(k):
    # golden-angle hues + rotating lightness/saturation so even ~24 branches stay
    # perceptually distinct, muted to fit the paper theme
    ls = [0.44, 0.56, 0.66]; ss = [0.55, 0.42, 0.48]
    out = []
    for i in range(k):
        h = (i * 0.61803398875) % 1.0
        r, g, b = colorsys.hls_to_rgb(h, ls[i % 3], ss[i % 3])
        out.append('%02x%02x%02x' % (int(r*255), int(g*255), int(b*255)))
    return out

def distinctive_terms(names, labels, cids):
    """Top c-TF-IDF terms per cluster from the law names (fallback labels)."""
    docs = {c: ' '.join(n.lower() for n, l in zip(names, labels) if l == c) for c in cids}
    vec = TfidfVectorizer(token_pattern=r'[a-záéíóúñ]{4,}',
                          stop_words=list(STOP))
    X = vec.fit_transform([docs[c] for c in cids])
    vocab = np.array(vec.get_feature_names_out())
    terms = {}
    for row, c in enumerate(cids):
        top = X[row].toarray()[0].argsort()[::-1][:6]
        terms[c] = [vocab[i] for i in top if X[row, i] > 0]
    return terms

# Curated materia names (real Mexican legal practice), keyed by cluster id.
# Deterministic clustering (random_state=42) → stable ids; overrides LLM naming.
MANUAL_LABELS = {
    0:  'Derecho Procesal',
    1:  'Derecho Militar',
    2:  'Derecho Fiscal',
    3:  'Hacienda y Finanzas Públicas',
    4:  'Fondos y Protección Financiera',
    5:  'Derecho Laboral y Seguridad Social',
    6:  'Banca de Desarrollo',
    7:  'Derecho Administrativo General',
    8:  'Derecho Cultural',
    9:  'Derecho Educativo',
    10: 'Administración Pública Federal',
    11: 'Derecho Electoral y Parlamentario',
    12: 'Grupos Vulnerables y Salud',
    13: 'Derecho Constitucional',
    14: 'Actividades Reguladas del Estado',
    15: 'Derecho Bancario',
    16: 'Mercado de Valores y Seguros',
    17: 'Desarrollo Rural y Social',
    18: 'Derecho Energético',
    19: 'Ambiental y Sanidad Agropecuaria',
    20: 'Comercio Exterior y Transporte',
    21: 'Seguridad Pública y Víctimas',
    22: 'Derecho Penal',
    23: 'Contratación y Regulación Pública',
    24: 'Telecomunicaciones y Medios',
    25: 'Transparencia y Datos Personales',
}

def name_with_llm(law_names, terms):
    """Ask DeepSeek for a short materia label; fall back to the top terms."""
    fallback = ', '.join(terms[:3]).title() if terms else 'Otras'
    if not DEEPSEEK_KEY:
        return fallback
    import requests
    sample = '\n'.join(f'- {n}' for n in law_names[:16])
    prompt = ("Estas leyes mexicanas forman un grupo temático. Dame SOLO un nombre "
              "de materia jurídica de 2 a 4 palabras que lo describa, sin comillas ni "
              f"explicación.\n\n{sample}")
    try:
        r = requests.post('https://api.deepseek.com/chat/completions', timeout=40,
            headers={'Authorization': f'Bearer {DEEPSEEK_KEY}'},
            json={'model': os.environ.get('DS_MODEL', 'deepseek-v4-flash'), 'temperature': 0.2,
                  'messages': [{'role': 'user', 'content': prompt}]})
        r.raise_for_status()
        label = r.json()['choices'][0]['message']['content'].strip().strip('"').split('\n')[0]
        return label[:48] or fallback
    except Exception as e:
        print(f"  · LLM naming failed ({e}); using terms")
        return fallback

def main():
    print("Building per-law embeddings…")
    names, X = law_vectors()
    print(f"  {len(names)} laws, dim {X.shape[1]}")

    print("UMAP → HDBSCAN…")
    reduced = umap.UMAP(n_components=10, n_neighbors=15, min_dist=0.0,
                        metric='cosine', random_state=42).fit_transform(X)
    labels = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=1,
                             cluster_selection_method='eom').fit_predict(reduced)

    # Reassign noise (-1) to the nearest cluster centroid so there's no grey dump.
    cids = sorted(c for c in set(labels) if c != -1)
    cents = {c: reduced[labels == c].mean(axis=0) for c in cids}
    for i in range(len(labels)):
        if labels[i] == -1:
            labels[i] = min(cids, key=lambda c: np.linalg.norm(reduced[i] - cents[c]))
    labels = np.array(labels)
    cids = sorted(set(labels.tolist()))
    print(f"  {len(cids)} clusters (sizes: {sorted((labels==c).sum() for c in cids)})")

    coords2d = umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.25,
                         metric='cosine', random_state=42).fit_transform(X)

    terms = distinctive_terms(names, labels, cids)
    colors = palette(len(cids))

    clusters, law_clusters, coords = {}, {}, {}
    for pos, c in enumerate(cids):
        members = [names[i] for i in range(len(names)) if labels[i] == c]
        print(f"  cluster {c}: {len(members)} leyes · {', '.join(terms[c][:4])}")
        label = MANUAL_LABELS.get(c) or name_with_llm(members, terms[c])
        cid = f'k{c}'
        clusters[cid] = {'label': label, 'color': colors[pos], 'size': len(members),
                         'terms': terms[c], 'laws': members}
        for m in members:
            law_clusters[m] = cid

    # scale UMAP 2D coords to a canvas for the initial layout
    xy = np.array(coords2d)
    xy = (xy - xy.mean(0)) / (xy.std(0) + 1e-9) * 900
    for i, n in enumerate(names):
        coords[n] = [float(xy[i, 0]), float(xy[i, 1])]

    out = {'law_clusters': law_clusters, 'clusters': clusters, 'coords': coords}
    json.dump(out, open(os.path.join(WEB, 'clusters.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    print(f"\n→ {WEB}/clusters.json  ({len(clusters)} ramas, "
          f"{'DeepSeek' if DEEPSEEK_KEY else 'términos'} naming)")

if __name__ == '__main__':
    main()
