#!/usr/bin/env python3
"""
Single source of truth for law text.

The Separado/*.json files carry the law name + metadata, but their
TEXTO VIGENTE.Contenido is truncated to a header for most laws. The real,
clean full text lives in datos/TextoPlano/*.txt. This module matches each
plain-text file to a law name (by the title in its header) and returns the
best available body per law, falling back to the JSON text when unmatched.
"""
import os, re, json, unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'datos', 'Separado')
PLAIN = os.path.join(ROOT, 'datos', 'TextoPlano')

def fix_moji(s):
    try:
        r = s.encode('latin1').decode('utf-8')
        return r if '�' not in r else s
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s

def clean_text(t):
    """Repair PDF-extraction damage: de-hyphenate words split across line breaks
    ('administra-\\nción' → 'administración'), drop font-glyph garbage (Private Use
    Area), and tidy runaway whitespace. Dates and numbered lists are preserved."""
    t = unicodedata.normalize('NFC', t)
    t = ''.join(' ' if 0xE000 <= ord(c) <= 0xF8FF else c for c in t)
    t = re.sub(r'([a-záéíóúñ])-\s*\n\s*([a-záéíóúñ])', r'\1\2', t)   # cut letters
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'(?:[ \t]*\n){3,}', '\n\n', t)
    return t.strip()

def norm(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]', ' ', re.sub(r'\s+', ' ', s).strip().lower()).strip()

# Two recovered titles carry a U+FFFD where the source PDF had a bad byte; the
# names are well-known, so repair them explicitly.
_NAME_FIX = {
    'LEY GENERAL PARA LA PREVENCI�N Y GESTI�N INTEGRAL DE LOS RESIDUOS':
        'LEY GENERAL PARA LA PREVENCIÓN Y GESTIÓN INTEGRAL DE LOS RESIDUOS',
    'LEY DE BIOSEGURIDAD DE ORGANISMOS GEN�TICAMENTE MODIFICADOS':
        'LEY DE BIOSEGURIDAD DE ORGANISMOS GENÉTICAMENTE MODIFICADOS',
}

_TITLE = re.compile(
    r'^\s*((?:LEY|C[OÓ]DIGO|CONSTITUCI[OÓ]N|REGLAMENTO|ESTATUTO|DECRETO|LINEAMIENTOS?)\b[^\n]{6,120})',
    re.M)

def _json_body(d):
    v = d.get('TEXTO VIGENTE', {}).get('Contenido', '') or ''
    t = d.get('Títulos', {}).get('Transitorio', {}).get('Contenido', '') or ''
    return fix_moji(v if len(v) >= len(t) else t)

def load():
    """Return {law_name: full_text}. Names are mojibake-fixed."""
    names, json_text = {}, {}
    for fn in sorted(os.listdir(DATA)):
        if not fn.endswith('.json') or 'WF' in fn:
            continue
        try:
            d = json.load(open(os.path.join(DATA, fn), encoding='utf-8', errors='replace'))
        except Exception:
            continue
        nm = fix_moji(d.get('Nombre', '').strip())
        if not nm:
            continue
        names[norm(nm)] = nm
        json_text[nm] = _json_body(d)

    plain = {}      # matched law_name -> plain text (preferred)
    recovered = {}  # plain-only laws whose JSON Nombre is missing/mislabeled
    for fn in sorted(os.listdir(PLAIN)):
        txt = open(os.path.join(PLAIN, fn), encoding='utf-8', errors='replace').read()
        m = _TITLE.search(txt[:1500].upper())
        if not m:
            continue
        key = norm(m.group(1))
        hit = names.get(key)
        if not hit:
            for nk, nm in names.items():
                if nk.startswith(key[:30]) or key.startswith(nk[:30]):
                    hit = nm
                    break
        clean = re.sub(r'\n{3,}', '\n\n', txt).strip()
        if hit:
            if len(clean) > len(plain.get(hit, '')):
                plain[hit] = clean
        else:
            # No JSON match: several major codes (Civil, Penal, Fiscal, CNPP…) live
            # only as plain text because their Separado Nombre is empty or mislabeled.
            # Recover them under the title from the header so they aren't lost.
            title = ' '.join(fix_moji(m.group(1)).split())
            title = _NAME_FIX.get(title, title)
            if len(clean) > len(recovered.get(title, '')):
                recovered[title] = clean

    out = {}
    for nm in json_text:
        body = clean_text(plain.get(nm) or json_text[nm])
        if len(body) >= 400:
            out[nm] = body
    for nm, txt in recovered.items():
        body = clean_text(txt)
        if len(body) >= 400 and nm not in out:
            out[nm] = body
    return out

if __name__ == '__main__':
    laws = load()
    from_plain = sum(1 for n in laws)  # rough
    print(f"laws with body: {len(laws)}")
    sizes = sorted(len(v) for v in laws.values())
    print(f"body size: min={sizes[0]} median={sizes[len(sizes)//2]} max={sizes[-1]}")
