# AmoxtliLex

Explorador semántico y grafo de conocimiento de la legislación federal mexicana.
Combina un **grafo interactivo** de leyes, materias e instituciones, una **búsqueda
semántica** en español y un **asistente conversacional** (DeepSeek) anclado en el
grafo. Pensado para público general, estudiantes de Derecho y profesionales con
consultas rápidas.

*Amoxtli* significa "libro" o "códice" en náhuatl.

---

## Qué hace

- **Grafo de conocimiento.** 299 leyes, 382 instituciones públicas y sus relaciones
  reales: 3 588 citas entre leyes (una ley que remite a otra) y 2 351 vínculos
  ley–institución. Las leyes se agrupan en 14 materias del derecho mexicano.
- **Genealogía normativa.** 115 leyes registran qué norma previa *abrogaron*
  (por ejemplo, la Ley de Concursos Mercantiles reemplazó a la Ley de Quiebras y de
  Suspensión de Pagos), extraído de los artículos transitorios.
- **Búsqueda semántica.** Consulta por significado, no por coincidencia exacta de
  palabras, sobre 13 542 fragmentos del texto vigente. Se pagina con Enter.
- **Asistente jurídico.** Chat estilo conversacional que responde con base en el
  grafo (materia, leyes citadas, instituciones y abrogaciones) más los pasajes
  relevantes recuperados. Usa la API de DeepSeek.

---

## Arquitectura

```
datos/                         corpus fuente (no versionado)
  Separado/*.json      → nombre de la ley + metadatos
  TextoPlano/*.txt     → texto vigente completo (fuente real)
        │
        ▼
corpus.py    empareja cada .txt con su ley y entrega el texto completo
        │
        ├── build_topics.py  → topics.json        (clasificación por materia)
        ├── build_kg.py      → graph*.json,        (grafo: leyes, instituciones,
        │                       laws_index.json      citas, abrogaciones)
        └── build_rag.py     → search.index,       (índice semántico FAISS)
                                chunks.pkl
        │
        ▼
server.py    API Flask: búsqueda + grafo + chat (DeepSeek)
web/index.html   interfaz (grafo vis-network, búsqueda, chat)
```

**Detalle importante del corpus.** El campo `TEXTO VIGENTE` de los JSON está
truncado a un encabezado en la mayoría de las leyes; el texto completo real vive en
`datos/TextoPlano/*.txt`. `corpus.py` es la única fuente de verdad y empareja ambos
(≈299/301 leyes). Los transitorios se conservan y se indexan junto con el articulado.

---

## Requisitos

- Python 3.10+
- Una clave de API de DeepSeek (para el chat): https://platform.deepseek.com
- Dependencias en `requirements.txt` (Flask, FAISS, sentence-transformers, requests, numpy)

---

## Instalación y ejecución

```bash
pip install -r requirements.txt

# Clave para el asistente (el resto de la app funciona sin ella)
export DEEPSEEK_API_KEY=sk-...

python3 server.py
# → http://localhost:8765
```

El primer arranque descarga el modelo de *embeddings*
(`paraphrase-multilingual-MiniLM-L12-v2`, ~470 MB) y tarda unos segundos en cargar
el índice. Los índices ya vienen construidos en `web/`, así que la aplicación es
funcional al clonar; el chat requiere la clave de DeepSeek.

---

## Reconstruir los índices

El corpus fuente (`datos/`, ~300 MB) **no se incluye** en el repositorio por su
tamaño. Con el corpus presente, el pipeline se regenera en orden:

```bash
python3 build_topics.py   # topics.json      (segundos)
python3 build_kg.py       # grafo + laws_index (segundos)
python3 build_rag.py      # índice semántico  (~13 min en CPU, 13 542 fragmentos)
```

---

## API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET  | `/api/search?q=…&k=40` | Búsqueda semántica; lista ordenada por similitud. |
| POST | `/api/chat` | Chat anclado en el grafo. Cuerpo: `{message, history}`. |
| GET  | `/api/graph/level0` | Nodos de materia (nivel superior). |
| GET  | `/api/graph/continent/<id>` | Leyes e instituciones de una materia. |
| GET  | `/api/law/<nombre>` | Ficha de una ley: materia, citas, instituciones, abrogaciones. |
| GET  | `/api/topics` | Clasificación de leyes por materia. |

---

## Estructura del repositorio

```
corpus.py          Carga y limpieza del texto de las leyes (fuente única)
build_topics.py    Clasificación por materia (14 áreas del derecho)
build_kg.py        Construcción del grafo de conocimiento
build_rag.py       Índice de búsqueda semántica (FAISS)
server.py          Servidor Flask (API + estáticos)
web/
  index.html       Interfaz de una sola página
  graph*.json      Grafo precomputado (leyes, instituciones, materias)
  laws_index.json  Ficha por ley (citas, instituciones, abrogaciones)
  topics.json      Clasificación por materia
  chunks.pkl       Fragmentos de texto para búsqueda
  search.index     Índice vectorial FAISS
```

---

## Limitaciones conocidas

- La clasificación por materia es por reglas léxicas; algunas leyes multitemáticas
  quedan en un área discutible.
- Unas pocas leyes tienen texto fuente ruidoso en el corpus, por lo que su lista de
  instituciones puede incluir alguna mención incidental.
- Las abrogaciones apuntan con frecuencia a leyes previas ya derogadas, que no son
  nodos del grafo; se muestran como atributo de la ley (su linaje), no como arista.
- El asistente responde solo con el contexto recuperado; no sustituye asesoría legal.

---

## Datos

Legislación federal mexicana (dominio público). El corpus procesado no se distribuye
en este repositorio por su tamaño.
