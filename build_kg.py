#!/usr/bin/env python3
"""
Build a real legal knowledge graph from the Mexican law corpus.

Signal, not noise:
  - Reads the substantive law body (TEXTO VIGENTE or Transitorio, whichever is larger),
    NOT the decree signature block.
  - Nodes: laws (grouped/coloured by materia) + institutions actually named in the text.
  - Edges: law -> law citations (real legal cross-references) and law -> institution.
  - Drops signatory names, dates and generic topic words entirely.

Outputs (consumed by server.py):
  graph.json          full graph (law + institution nodes, edges)
  graph_multi.json    {level0: continent nodes, full: graph}
  graph_levels.json   {continents: {cid: [law nodes]}, law_topics}
  laws_index.json     per-law {name, materia, references, institutions, size}

Run build_topics.py first (produces topics.json with the materia classification).
"""
import json, os, re, unicodedata
from collections import defaultdict
import corpus

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'datos', 'Separado')
OUT = os.path.join(ROOT, 'web')
INST_COLOR = '35766a'          # institutions
LAW_LABEL_MAX = 46

def fix_moji(s):
    try:
        r = s.encode('latin1').decode('utf-8')
        return r if '�' not in r else s
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s

def norm(s):
    """lowercase, strip accents, collapse whitespace — for matching only."""
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s).strip().lower()

# Institutions: named public bodies. Head word + up to 6 following title-case / connector tokens.
INST_RE = re.compile(
    r'\b(Instituto|Comisi[oó]n|Consejo|Secretar[ií]a|Tribunal|Procuradur[ií]a|Fiscal[ií]a|'
    r'Banco de M[eé]xico|Suprema Corte|Auditor[ií]a Superior|Servicio de Administraci[oó]n Tributaria|'
    r'Junta|Registro|Sistema Nacional|Fondo|Comit[eé]|Direcci[oó]n General)'
    r'(?:\s+(?:de|del|de la|de los|de las|para|y|e|en|Nacional|General|Federal|'
    r'[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)){1,6}')

# Boilerplate bodies that appear in nearly every law — carry no discriminating signal.
INST_BLOCK = {norm(x) for x in [
    'Comisión Permanente', 'Consejo de', 'Secretaría de', 'Servicio de Administración Tributaria de',
    'Comisión de', 'Instituto de', 'Consejo General', 'Junta de', 'Registro de', 'Fondo de',
    'Comité de', 'Dirección General de', 'Secretaría de la', 'Comisión Nacional', 'Instituto Nacional',
]}
INST_TAIL = re.compile(r'\s+(?:de|del|de la|de los|de las|para|y|e|en|la|el)$', re.I)

# Whole-law abrogation stated in a law's transitorios: "se abroga la Ley/Código X ...".
# This is the law's genealogy — what prior law it replaced. Distinct from a citation.
ABROGA_RE = re.compile(
    r'\bse\s+abroga\w*\s+(?:el|la|los|las)?\s*'
    r'((?:LEY|C[ÓO]DIGO|REGLAMENTO|ESTATUTO)\b[^.\n;]{4,90})', re.I)
_ABROGA_TAIL = re.compile(r'\s+(?:publicad|de fecha|expedid|del?\s+\d|,).*$', re.I)

def abrogations(text):
    m = re.search(r'\bTRANSITORIOS?\b', text, re.I)
    trans = text[m.start():] if m else ''
    out = []
    for a in ABROGA_RE.finditer(trans):
        name = _ABROGA_TAIL.sub('', re.sub(r'\s+', ' ', a.group(1)).strip()).strip(' ,.')
        # keep only the first "... y la Ley ..." conjunct as one target; drop trailing clauses
        name = re.split(r'\s+y\s+la\s+', name)[0].strip()
        if len(name) >= 8 and name not in out:
            out.append(name)
    return out

def clean_inst(s):
    s = re.sub(r'\s+', ' ', s).strip()
    prev = None
    while prev != s:                       # strip dangling trailing connectors ("... de")
        prev = s
        s = INST_TAIL.sub('', s).strip()
    return s

def main():
    topics = json.load(open(os.path.join(OUT, 'topics.json'), encoding='utf-8'))
    law_topics = topics['law_topics']                      # name -> cid
    continents = topics['continents']                      # cid -> {label,color,...}

    laws = corpus.load()                                   # name -> real full text
    names = list(laws)
    print(f"Laws with substantive body: {len(names)}")

    # ── law -> law references (citation graph) ──────────────────────────────
    # Match each law's full normalized name inside every other law's text. Verbatim = high precision.
    ref_index = []                         # (cid_norm, min_len, canonical_name)
    for n in names:
        nn = norm(n)
        if len(nn) >= 12:
            ref_index.append((nn, n))
    # Constitution is cited constantly by short forms:
    CONST = next((n for n in names if 'constitucion politica' in norm(n)), None)

    references = defaultdict(set)          # name -> set(referenced names)
    for src in names:
        text = norm(laws[src])
        for nn, tgt in ref_index:
            if tgt == src:
                continue
            if nn in text:
                references[src].add(tgt)
        if CONST and src != CONST and re.search(r'\bconstitucion\b', text):
            references[src].add(CONST)

    # ── law -> institution ─────────────────────────────────────────────────
    inst_laws = defaultdict(set)           # institution -> set(law names)
    for src in names:
        seen = set()
        for m in INST_RE.finditer(laws[src]):
            inst = clean_inst(m.group(0))
            if len(inst) < 12:
                continue
            key = norm(inst)
            if key in INST_BLOCK or len(key.split()) < 2:
                continue
            seen.add((key, inst))
        for key, inst in seen:
            inst_laws[key].add(src)

    # keep institutions shared by 2+ laws but drop hyper-hubs (boilerplate present everywhere)
    hub_cut = max(6, int(0.12 * len(names)))
    inst_keep = {}                         # key -> (display, laws)
    canon = {}                             # key -> best display spelling
    for src in names:
        for m in INST_RE.finditer(laws[src]):
            inst = clean_inst(m.group(0)); key = norm(inst)
            if key in inst_laws and (key not in canon or len(inst) < len(canon[key])):
                canon[key] = inst
    for key, docs in inst_laws.items():
        if 2 <= len(docs) <= hub_cut:
            inst_keep[key] = (canon.get(key, key), docs)
    print(f"Institutions kept: {len(inst_keep)} (hub cut >{hub_cut} laws)")

    # ── build graph ─────────────────────────────────────────────────────────
    def color_obj(hexc):
        hexc = '#' + hexc.lstrip('#')
        dark = '#' + ''.join(f'{max(0,int(hexc[1:][i:i+2],16)-40):02x}' for i in (0,2,4))
        return {'background': hexc, 'border': dark,
                'highlight': {'background': dark, 'border': dark},
                'hover': {'background': dark, 'border': dark}}

    law_id = {n: f'law_{i}' for i, n in enumerate(names)}
    nodes, edges, level_laws = [], [], defaultdict(list)

    for n in names:
        cid = law_topics.get(n, 'otras')
        cont = continents.get(cid, {'label': 'Disposiciones Generales', 'color': '95a5a6'})
        deg = len(references[n]) + sum(1 for k in inst_keep if n in inst_keep[k][1])
        size = max(10, min(48, 10 + deg * 1.6))
        node = {'id': law_id[n], 'label': n[:LAW_LABEL_MAX], 'title': n, 'group': 'law',
                'size': size, 'value': len(references[n]),
                'continent': cid, 'continent_label': cont['label'], 'continent_color': cont['color'],
                'color': color_obj(cont['color'])}
        nodes.append(node)
        level_laws[cid].append(node)

    for key, (disp, docs) in inst_keep.items():
        eid = f'inst_{len(nodes)}'
        nodes.append({'id': eid, 'label': disp[:38], 'title': f'{disp} · {len(docs)} leyes',
                      'group': 'org', 'size': max(6, min(26, len(docs) * 2)), 'value': len(docs),
                      'color': color_obj(INST_COLOR)})
        for d in docs:
            edges.append({'from': law_id[d], 'to': eid, 'label': 'regula'})

    for src, tgts in references.items():
        for t in tgts:
            edges.append({'from': law_id[src], 'to': law_id[t], 'label': 'referencia', 'dashes': True})

    print(f"Nodes: {len(nodes)} (laws {len(names)}, inst {len(inst_keep)})  Edges: {len(edges)} "
          f"(ref {sum(len(v) for v in references.values())}, inst {len(edges)-sum(len(v) for v in references.values())})")

    # continent (level0) nodes
    level0 = []
    for cid, c in continents.items():
        if not c.get('size'):
            continue
        level0.append({'id': f'cont_{cid}', 'label': c['label'], 'group': 'continent',
                       'size': max(20, min(70, 15 + c['size'] * 1.2)), 'value': c['size'],
                       'continent_id': cid, 'color': color_obj(c['color'])})

    full = {'nodes': nodes, 'edges': edges}
    json.dump(full, open(os.path.join(OUT, 'graph.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump({'level0': {'nodes': level0, 'edges': []}, 'full': full},
              open(os.path.join(OUT, 'graph_multi.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump({'continents': dict(level_laws), 'law_topics': law_topics},
              open(os.path.join(OUT, 'graph_levels.json'), 'w', encoding='utf-8'), ensure_ascii=False)

    index = []
    for n in names:
        cid = law_topics.get(n, 'otras')
        index.append({'name': n, 'materia': continents.get(cid, {}).get('label', '—'),
                      'references': sorted(references[n]),
                      'institutions': sorted(canon.get(k, k) for k in inst_keep if n in inst_keep[k][1]),
                      'abrogates': abrogations(laws[n]),
                      'size': len(laws[n])})
    json.dump(index, open(os.path.join(OUT, 'laws_index.json'), 'w', encoding='utf-8'), ensure_ascii=False)

    # quick sanity report
    top = sorted(inst_keep.items(), key=lambda kv: -len(kv[1][1]))[:10]
    print("\nTop institutions (by #laws):")
    for k, (disp, docs) in top:
        print(f"  {len(docs):3d}  {disp}")
    print(f"\nDone → graph.json, graph_multi.json, graph_levels.json, laws_index.json")

if __name__ == '__main__':
    main()
