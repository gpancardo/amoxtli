#!/usr/bin/env python3
"""Clasificación académica de leyes mexicanas por análisis léxico-jurídico."""
import json, os, re
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'datos', 'Separado')
OUT = os.path.join(ROOT, 'web')

def fix_moji(s):
    # Source text is double-encoded UTF-8; latin1 roundtrip repairs it.
    try:
        r = s.encode('latin1').decode('utf-8')
        return r if '�' not in r else s
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s

# Clasificación académica estándar del derecho mexicano
# Estructura: (id, nombre, color, {palabras_clave: peso})
CONTINENTS = [
    ('constitucional', 'Derecho Constitucional', '8B7EC8', {
        'constitución': 10, 'constitucional': 8, 'amparo': 9,
        'derechos humanos': 10, 'derechos fundamentales': 9,
        'garantías individuales': 8, 'libertad': 6, 'nacionalidad': 7,
        'poder legislativo': 7, 'poder judicial': 7, 'poder ejecutivo': 7,
        'división de poderes': 8, 'federalismo': 7, 'soberanía': 7,
        'reforma constitucional': 8, 'consulta popular': 7,
        'comisión nacional de los derechos humanos': 8, 'cndh': 8,
        'iniciativa': 5, 'formación de leyes': 6,
    }),
    ('penal', 'Derecho Penal y Justicia', 'd63031', {
        'penal': 10, 'delito': 9, 'delitos': 9, 'crimen': 8,
        'justicia penal': 10, 'procedimientos penales': 10,
        'código penal': 10, 'ejecución penal': 9,
        'desaparición forzada': 9, 'tortura': 8,
        'extradición': 8, 'extinción de dominio': 8,
        'seguridad pública': 7, 'seguridad nacional': 7,
        'readaptación social': 7, 'reinserción': 6,
        'sentencia': 6, 'tribunal': 6, 'juez': 6,
        'ministerio público': 7, 'fiscalía': 7,
        'víctimas': 7, 'protección a víctimas': 7,
        'responsabilidad patrimonial': 6,
        'responsabilidades administrativas': 6,
        'justicia militar': 8, 'código de justicia militar': 8,
        'procedimiento contencioso': 6, 'justicia cotidiana': 7,
    }),
    ('fiscal', 'Derecho Fiscal y Tributario', 'E06848', {
        'fiscal': 10, 'fiscales': 10, 'tributario': 9, 'tributación': 9,
        'impuesto': 10, 'impuestos': 10, 'aduanera': 9, 'aduanas': 9,
        'comercio exterior': 8, 'contribución': 8, 'contribuciones': 8,
        'ingresos de la federación': 9, 'ingresos sobre hidrocarburos': 9,
        'coordinación fiscal': 9, 'fiscalización': 8,
        'rendición de cuentas': 7, 'disciplina financiera': 7,
        'presupuesto de egresos': 8, 'gasto público': 7,
        'contabilidad gubernamental': 8,
        'ley de ingresos': 9, 'código fiscal': 10,
        'hacienda': 7, 'tesorería': 6,
        'deuda pública': 7, 'empréstitos': 6,
    }),
    ('financiero', 'Derecho Financiero y Bancario', '00A8A8', {
        'banco': 10, 'banca': 10, 'bancario': 10, 'financiero': 9,
        'crédito': 9, 'ahorro': 9, 'seguros': 10, 'fianzas': 10,
        'inversión': 8, 'valores': 9, 'mercado de valores': 10,
        'sociedades de inversión': 9, 'concursos mercantiles': 9,
        'instituciones de crédito': 10, 'instituciones financieras': 9,
        'adquisiciones': 7, 'arrendamientos': 7,
        'cámaras empresariales': 8, 'empresarial': 7,
        'cooperativas': 7, 'fondos de aseguramiento': 8,
        'ahorro y crédito popular': 9,
        'banco de méxico': 10, 'banxico': 10,
        'protección al ahorro': 8, 'protección al consumidor': 7,
        'sistema financiero': 9, 'servicios financieros': 8,
    }),
    ('laboral', 'Derecho Laboral y Seguridad Social', '00b894', {
        'trabajo': 10, 'laboral': 10, 'trabajadores': 10,
        'seguridad social': 10, 'pensiones': 9, 'jubilaciones': 9,
        'issste': 10, 'imss': 10, 'infonavit': 10,
        'salario': 8, 'empleo': 8, 'sindicato': 8,
        'contratos colectivos': 9, 'huelga': 7,
        'prestaciones': 7, 'indemnización': 7,
        'instituto de seguridad social': 10,
        'riesgos de trabajo': 8, 'enfermedades profesionales': 7,
        'protección al trabajador': 8, 'justicia laboral': 9,
        'conciliación y arbitraje': 8,
        'instituto del fondo nacional': 8,
    }),
    ('electoral', 'Derecho Electoral', '6c5ce7', {
        'electoral': 10, 'elecciones': 9, 'electorales': 10,
        'partidos políticos': 10, 'voto': 9, 'sufragio': 8,
        'consulta popular': 8, 'plebiscito': 7, 'referéndum': 7,
        'medios de impugnación': 9, 'delitos electorales': 9,
        'instituto nacional electoral': 10, 'ine': 9,
        'tribunal electoral': 9, 'procedimientos electorales': 10,
        'campañas': 7, 'precampañas': 7,
        'fiscalización electoral': 8,
        'sistema de medios de impugnación': 9,
        'representación proporcional': 7,
    }),
    ('ambiental', 'Derecho Ambiental y Agrario', '4a9e5e', {
        'ambiente': 10, 'ambiental': 10, 'ecológico': 9, 'ecología': 8,
        'agraria': 9, 'agrario': 9, 'rural': 8, 'campo': 7,
        'agua': 8, 'aguas nacionales': 9, 'forestal': 8,
        'pesca': 8, 'energía': 7, 'geotérmica': 7,
        'desarrollo rural': 8, 'sustentable': 7, 'sostenible': 7,
        'caña de azúcar': 7, 'procampo': 8,
        'agricultura': 7, 'ganadería': 7,
        'cambio climático': 8, 'residuos': 7,
        'biodiversidad': 8, 'áreas naturales protegidas': 8,
        'impacto ambiental': 8, 'vida silvestre': 7,
        'energía para el campo': 8, 'electrificación rural': 7,
        'minera': 9, 'minería': 9, 'minero': 8, 'yacimientos': 8,
        'subsuelo': 8, 'reservas mineras': 9, 'hidrocarburos': 8,
        'petróleo': 7, 'petróleos': 7, 'nuclear': 7, 'geología': 6,
    }),
    ('salud', 'Derecho Sanitario y Asistencial', '74b9ff', {
        'salud': 10, 'sanitario': 9, 'sanidad': 8,
        'asistencia social': 9, 'asistencial': 8,
        'protección civil': 7, 'protección a la salud': 9,
        'cultura física': 7, 'deporte': 7,
        'institutos nacionales de salud': 10,
        'alimentaria': 7, 'desarrollo social': 7,
        'asentamientos humanos': 7, 'vivienda': 7,
        'atención a víctimas': 6,
        'desarrollo integral': 6, 'bienestar': 6,
        'prevención de enfermedades': 7, 'epidemiología': 7,
    }),
    ('educacion', 'Derecho Educativo y Cultural', 'fdcb6e', {
        'educación': 10, 'educativo': 9, 'educativa': 9,
        'ciencia': 9, 'científico': 8, 'tecnología': 8,
        'cultura': 8, 'cultural': 8, 'libro': 7, 'lectura': 7,
        'bibliotecas': 8, 'investigación': 7,
        'innovación': 7, 'fomento a la lectura': 8,
        'sociedades de solidaridad social': 7,
        'cooperación internacional para el desarrollo': 7,
        'patrimonio cultural': 7, 'bellas artes': 7,
        'propiedad intelectual': 7, 'derechos de autor': 7,
        'ciencia y tecnología': 9,
        'cinematografía': 9, 'cine': 7, 'cinematográfica': 8,
    }),
    ('comunicaciones', 'Derecho de Comunicaciones y Transporte', 'E8A838', {
        'telecomunicaciones': 10, 'comunicaciones': 9,
        'radiodifusión': 10, 'radio': 8, 'televisión': 8,
        'internet': 7, 'banda ancha': 7,
        'transporte': 9, 'caminos': 8, 'puentes': 8,
        'autotransporte': 9, 'carretero': 7,
        'aviación': 9, 'aeropuertos': 9, 'aeronáutica': 8,
        'navegación': 8, 'marítimo': 7,
        'ferrocarril': 8, 'ferroviario': 8,
        'puertos': 8, 'correos': 7,
        'firma electrónica': 8, 'digital': 6,
        'movilidad': 6, 'tránsito': 6,
        'espectro radioeléctrico': 8, 'concesiones': 6,
    }),
    ('militar', 'Derecho Militar y Defensa Nacional', '636e72', {
        'militar': 10, 'militares': 10, 'ejército': 10,
        'armada': 10, 'fuerza aérea': 10,
        'defensa nacional': 10, 'marina': 9,
        'ascensos': 8, 'recompensas': 7,
        'disciplina del ejército': 9, 'disciplina militar': 9,
        'educación militar': 9, 'educación naval': 9,
        'servicio militar': 9, 'seguridad social fuerzas armadas': 10,
        'instituto de seguridad social para las fuerzas': 10,
        'ley orgánica de la armada': 10,
        'ley orgánica del ejército': 10,
        'personal de la armada': 8,
    }),
    ('administrativo', 'Derecho Administrativo y Transparencia', '0984e3', {
        'transparencia': 10, 'acceso a la información': 10,
        'archivos': 9, 'archivo general': 9,
        'protección de datos': 9, 'datos personales': 9,
        'mejora regulatoria': 8, 'simplificación administrativa': 7,
        'gobierno digital': 7, 'administración pública': 7,
        'procedimiento administrativo': 8, 'federal de procedimiento': 8,
        'entidades paraestatales': 7, 'organismos descentralizados': 7,
        'expropiación': 7, 'obra pública': 6,
        'servicio público': 6, 'función pública': 6,
        'responsabilidades de servidores públicos': 7,
        'ley orgánica de la administración': 8,
        'régimen de propiedad': 5,
    }),
    ('civil', 'Derecho Civil y Familiar', 'e17055', {
        'civil': 9, 'familiar': 9, 'familiares': 9,
        'procedimientos civiles': 10, 'código civil': 10,
        'personas adultas mayores': 7,
        'niñas niños y adolescentes': 8,
        'personas con discapacidad': 7,
        'asociaciones religiosas': 7,
        'culto público': 7, 'sociedades civiles': 6,
        'migración': 7, 'migratorio': 7,
        'refugiados': 8, 'asilo político': 8,
        'nacionalidad': 6, 'naturalización': 6,
        'registro civil': 7, 'nombre de las personas': 6,
        'protección de datos personales': 6,
        'premios estímulos y recompensas': 7,
    }),
    ('comercial', 'Derecho Comercial y Empresarial', 'FFB300', {
        'comercio': 9, 'comercial': 9, 'mercantil': 9,
        'empresarial': 8, 'empresas': 8,
        'sociedades mercantiles': 9, 'inversión extranjera': 7,
        'competencia económica': 8, 'protección al consumidor': 8,
        'propiedad industrial': 7, 'marcas': 6,
        'concursos mercantiles': 8, 'quiebra': 7,
        'cámaras de comercio': 7, 'confederaciones': 6,
        'normalización': 5, 'metrología': 5,
        'asociaciones público privadas': 7,
        'inversión de normas extranjeras': 6,
    }),
]

def classify_law(name, tf_dict):
    """Clasifica una ley por análisis de su nombre y vocabulario distintivo."""
    name_lower = name.lower()
    
    # Extraer palabras clave del TF (términos más frecuentes y distintivos)
    tf_words = Counter()
    if isinstance(tf_dict, dict):
        for word, freq in tf_dict.items():
            w = word.lower().strip()
            if len(w) > 3 and w.isalpha() and not w.isdigit():
                # Filtrar palabras funcionales irrelevantes
                if w not in {'artículo', 'artículos', 'art', 'fracción', 'fracciones',
                            'párrafo', 'párrafos', 'transitorio', 'transitorios',
                            'decreto', 'decretos', 'publicado', 'publicada',
                            'reforma', 'reformas', 'reforman', 'adiciona', 'adicionan',
                            'deroga', 'derogan', 'modifica', 'modifican',
                            'presente', 'siguiente', 'anteriores', 'señalado',
                            'establece', 'establecen', 'deberá', 'deberán',
                            'dispone', 'disponen', 'disposición', 'disposiciones',
                            'respectivo', 'respectiva', 'correspondiente',
                            'podrá', 'podrán', 'deberá', 'deberán',
                            'congreso', 'unión', 'cámara', 'diputados', 'senadores',
                            'federación', 'federal', 'federales',
                            'oficial', 'diario', 'entrará', 'vigor', 'surtirá',
                            'conforme', 'términos', 'efectos', 'aplicación',
                            'aplicable', 'aplicables', 'previsto', 'prevista'}:
                    tf_words[w] = freq
    
    # Whole-word matching: naive substring made 'ine' (INE, electoral) match
    # "cinematografía" and "minera", dumping them into Derecho Electoral.
    tf_text = ' ' + ' '.join(w for w, _ in tf_words.most_common(30)) + ' '

    best_score = 0
    best_continent = None

    for cid, clabel, ccolor, keywords in CONTINENTS:
        score = 0
        for kw, weight in keywords.items():
            pat = re.compile(r'\b' + re.escape(kw) + r'\b')
            if pat.search(name_lower):          # nombre: señal más fuerte
                score += weight * 3
            if pat.search(tf_text):             # vocabulario distintivo: señal secundaria
                score += weight * 0.5

        if score > best_score:
            best_score = score
            best_continent = (cid, clabel, ccolor)
    
    return best_continent

def main():
    files = sorted([f for f in os.listdir(DATA) if f.endswith('.json') and 'WF' not in f])
    
    law_topics = {}
    topics_data = {}
    
    for cid, clabel, ccolor, _ in CONTINENTS:
        topics_data[cid] = {'id': f'cont_{cid}', 'label': clabel, 'color': ccolor, 'laws': [], 'size': 0}
    
    for fname in files:
        try:
            with open(os.path.join(DATA, fname), 'r', encoding='utf-8', errors='replace') as f:
                d = json.load(f)
        except:
            continue
        name = fix_moji(d.get('Nombre', '').strip()) or fname.replace('.json', '')
        tf = d.get('TF', {})
        match = classify_law(name, tf)
        if match:
            cid, clabel, ccolor = match
            law_topics[name] = cid
            if cid not in topics_data:
                topics_data[cid] = {'id': f'cont_{cid}', 'label': clabel, 'color': ccolor, 'laws': [], 'size': 0}
            topics_data[cid]['laws'].append(name)
            topics_data[cid]['size'] += 1
    
    # Unclassified -> general
    for fname in files:
        try:
            with open(os.path.join(DATA, fname), 'r', encoding='utf-8', errors='replace') as f:
                d = json.load(f)
        except:
            continue
        name = fix_moji(d.get('Nombre', '').strip()) or fname.replace('.json', '')
        if name not in law_topics:
            cid_other = 'otras'
            if cid_other not in topics_data:
                topics_data[cid_other] = {'id': 'cont_otras', 'label': 'Disposiciones Generales', 'color': '95a5a6', 'laws': [], 'size': 0}
            law_topics[name] = cid_other
            topics_data[cid_other]['laws'].append(name)
            topics_data[cid_other]['size'] += 1
    
    topic_labels = {cid: data['label'] for cid, data in topics_data.items()}
    
    # Report
    print("=== Clasificación Académica de Leyes Mexicanas ===\n")
    sorted_conts = sorted(topics_data.items(), key=lambda x: -x[1]['size'])
    for cid, data in sorted_conts:
        bar = '█' * max(1, data['size'] // 2)
        print(f"  {data['label']:45s} {data['size']:3d}  {data['color']}  {bar}")
    print(f"\n  Total: {sum(d['size'] for d in topics_data.values())} leyes clasificadas")
    
    # Save
    result = {
        'law_topics': law_topics,
        'continents': topics_data,
        'topic_labels': topic_labels,
        'n_topics': len([c for c in topics_data if topics_data[c]['size'] > 0]),
    }
    with open(os.path.join(OUT, 'topics.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n→ {OUT}/topics.json")

if __name__ == '__main__':
    main()
