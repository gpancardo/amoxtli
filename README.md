# Amoxtli

Mapa semántico y buscador de la legislación federal mexicana. *Amoxtli* significa
"libro" o "códice" en náhuatl.

Amoxtli toma ~313 leyes federales vigentes y las vuelve navegables de tres formas
complementarias:

1. **Un mapa** donde cada ley es un nodo, agrupado por cercanía temática real
   (no por una taxonomía impuesta a mano) y conectado a las leyes que cita.
2. **Un buscador semántico** que encuentra documentos por significado, no por
   coincidencia exacta de palabras.
3. **Un asistente de consulta (Tlamatini)** que responde sobre el *contenido* de
   las leyes citando su texto, no inventando.

Todo corre localmente sobre un solo servidor Flask y un solo archivo HTML. La
única dependencia externa en tiempo de ejecución es la API de DeepSeek, y solo
para el chat.

## Origen y equipo

Amoxtli nació en el **hackatón de la Escuela de Verano RIEEE del CIC**, de donde
viene el dataset de legislación con el que trabaja. Lo construimos:

- **Germán Pancardo** — Ingeniería en Computación, UNAM.
- **Karim Vallejo** — Física, Facultad de Ciencias, UNAM.
- **Bruno Pancardo** — Derecho, UNITEC Campus Sur.

## Modelo de lenguaje

El chat (Tlamatini) y el nombrado automático de ramas usan la API de DeepSeek
con el modelo **`deepseek-v4-flash`** por defecto, configurable con la variable
`DS_MODEL`. La búsqueda semántica no usa DeepSeek: corre localmente con
`paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers).

---

## Cómo se ve

- **Grafo tipo Obsidian**: fuerza dirigida con posiciones sembradas por UMAP, así
  que la estructura semántica ya viene "resuelta" y la física solo le da vida
  mínima. Se congela al pasar el cursor para que los nodos sean fáciles de clicar.
- **Color = rama semántica**. No hay leyenda fija; al pasar el cursor sobre un
  nodo aparece un chip con la ley y su materia.
- **Buscar → página de resultados → lector**. El buscador sugiere documentos
  mientras escribes; Enter abre una página de resultados estilo Google; un clic
  abre el texto completo del documento.
- **Lector** con el texto real de la ley, resaltado de los términos buscados y
  salto automático a la primera coincidencia. Cada documento tiene URL propia
  (`#ley/NOMBRE`), así que es compartible.
- **Panel de ley**: rama, materia, leyes que cita (clicables), leyes que abroga
  e instituciones que menciona.

---

## Arquitectura

**Fuente de los datos.** El corpus proviene de un dataset publicado de legislación
mexicana en la revista *Data* (MDPI), 2022:
<https://www.mdpi.com/2306-5729/7/7/91>. Amoxtli no re-extrae los PDF del Diario
Oficial: parte de ese corpus (metadatos + texto plano) y lo procesa.

```
datos/                         Fuente cruda (dataset MDPI Data 2022)
  Separado/*.json              metadatos por ley + TF + texto (a menudo truncado)
  TextoPlano/*.txt             texto completo real, extraído de los PDF del DOF

corpus.py                      Fuente única de verdad del texto de cada ley

build_topics.py    → topics.json     materia por análisis léxico (metadato)
build_clusters.py  → clusters.json   ramas semánticas por embeddings (color/layout)
build_kg.py        → graph.json      grafo: citas, instituciones, abrogaciones
                     laws_index.json  ficha por ley
build_rag.py       → chunks.pkl      fragmentos + índice vectorial FAISS
                     search.index

server.py                      Flask: búsqueda, chat RAG, grafo, texto crudo
web/index.html                 Todo el frontend (un archivo, vis-network por CDN)
```

El orden del pipeline importa: `build_topics` → `build_rag` → `build_clusters` →
`build_kg`. Todos dependen de `corpus.py`; `build_clusters` lee el índice FAISS que
produce `build_rag`, y `build_kg` lee `topics.json` y `clusters.json`.

---

## Qué del dataset original NO usamos (y por qué)

El dataset trae más archivos de los que Amoxtli indexa. Nada se descarta por
descuido; esto es lo que se deja fuera y la razón:

- **Los 602 archivos `*WF*.json` (transitorios).** Parecen prometedores —en el
  derecho mexicano los artículos transitorios son decisivos (entrada en vigor,
  régimen de transición, plazos, qué versión aplica según la fecha)—, pero **no
  contienen el texto de los transitorios**: su campo `Transitorio` es un
  diccionario de **frecuencia de palabras** (`{"decreto": 59, "vigor": 28, …}`),
  un bag-of-words, no algo legible ni citable. Amoxtli trabaja con embeddings sobre
  texto real, así que esos conteos no le sirven. **Y no se pierde nada**: el texto
  de los transitorios —originales y de cada reforma— ya viene en el texto vigente
  de `TextoPlano`; 312 de 313 leyes lo incluyen, y ~1,987 fragmentos indexados lo
  contienen, así que es buscable, se lee y entra al contexto del chat.

- **La carpeta `datos/Semiestructurado/` (301 archivos).** Es una vista casi
  idéntica a `Separado` con el articulado troceado por títulos. `corpus.py` obtiene
  mejor texto de `TextoPlano` (completo y limpio), así que no se usa. No aporta
  leyes nuevas (salvo una que ya recuperamos por otra vía).

- **El campo `TEXTO VIGENTE.Contenido` de los JSON**, cuando existe texto plano.
  Está **truncado a un encabezado** para la mayoría de las leyes; solo se usa como
  respaldo cuando no hay archivo de `TextoPlano` que empate.

- **El campo `TF` (frecuencia de términos) de cada ley.** Se usa únicamente en
  `build_topics.py` para la clasificación por palabras clave (materia, un metadato
  secundario). El resto del sistema —búsqueda, clustering, chat— corre sobre
  embeddings del texto, no sobre conteos.

En resumen: usamos el **texto vigente completo** de las 313 leyes con cuerpo
sustantivo (incluidos sus transitorios) y descartamos las representaciones
derivadas (bag-of-words, TF) y las copias redundantes o truncadas.

---

## Decisiones técnicas y por qué

### 1. El texto real vive en `TextoPlano`, no en el JSON

Los `Separado/*.json` traen el nombre y metadatos de cada ley, pero su campo de
texto vigente está **truncado a un encabezado** para la mayoría. El texto completo
y limpio está en `datos/TextoPlano/*.txt`. `corpus.py` es la única pieza que
resuelve esto: empareja cada archivo de texto plano con un nombre de ley (por el
título en su encabezado, con respaldo por prefijo normalizado) y devuelve el mejor
cuerpo disponible, cayendo al JSON solo cuando no hay match. Cualquier otra parte
del sistema que necesite texto pasa por aquí. Regla registrada para no repetir el
error de leer el JSON truncado.

**Nota sobre emparejamiento nombre↔texto.** En unos pocos registros el campo
`Nombre` del JSON no coincide con el archivo de texto plano correspondiente (queda
vacío o hereda el nombre de otra ley), lo que haría que un puñado de ordenamientos
—incluidos algunos códigos federales— no se emparejaran y quedaran fuera. Para
aprovechar el corpus al máximo, `corpus.load` los conserva: cuando un archivo de
texto plano no empata con ningún `Nombre`, lo indexa como ley propia usando el
título de su encabezado. Así el corpus llega a **313 leyes** con cuerpo sustantivo,
incluidos todos los códigos.

### 2. Limpieza del texto: el daño real era de extracción de PDF

Los textos vienen de extraer PDF del Diario Oficial. El problema visible no era
mojibake (revisado: cero secuencias `Ã`/`Â`, cero caracteres de reemplazo), sino
**palabras cortadas en el salto de línea** — "administra-\nción" — 613 casos. La
función `corpus.clean_text`:

- Une palabras partidas por guion al final de renglón (`administra-\nción` →
  `administración`), respetando fechas (`11-08-2014`) y numerales (`2-\n1`).
- Elimina glifos basura del Área de Uso Privado (U+E000–U+F8FF): fórmulas mal
  extraídas que se ven como cajas ▯.
- Normaliza a NFC y colapsa espacios y saltos de línea excesivos.

Se aplica en `corpus.load`, así que beneficia al lector, a los fragmentos de
búsqueda y a los pasajes del chat por igual.

### 3. Ramas semánticas por embeddings, no taxonomía por palabras clave

Existe una clasificación por palabras clave (`build_topics.py`) que asigna a cada
ley una *materia* legal estándar. Sirve como metadato, pero como criterio visual
falla: el sustring `ine` (por INE, el instituto electoral) hacía match dentro de
"c**ine**matografía" y "m**ine**ra", mandando esas leyes a Derecho Electoral. Se
corrigió con coincidencia por límite de palabra, pero la lección es más general:
una taxonomía impuesta a mano no captura cómo las leyes realmente se parecen.

Por eso el color y el layout salen de **clustering por embeddings**
(`build_clusters.py`):

- Se promedian los vectores de todos los fragmentos de cada ley (reconstruidos del
  índice FAISS) para obtener un vector por ley.
- **UMAP** reduce a 10 dimensiones con métrica coseno.
- **HDBSCAN** agrupa: encuentra clusters *naturales* sin fijar el número a mano.
  El ruido se reasigna al centroide más cercano para que no haya un montón gris.
- Resultan **26 ramas** que sí agrupan por afinidad real (banca de desarrollo,
  penal y seguridad pública, energético, ambiental y sanidad agropecuaria, etc.).
- Un segundo UMAP a 2D da coordenadas para sembrar el layout del grafo.

### 4. Nombres de rama curados a mano

Los clusters no traen nombre legible. Se generan con DeepSeek a partir de las leyes
de cada grupo, pero se **sobrescriben con una lista curada** (`MANUAL_LABELS`) para
que coincidan con las materias que usan los abogados de verdad: "Derecho Fiscal",
"Derecho Penal y Seguridad Pública", "Mercado de Valores y Seguros", etc. El
clustering es determinista (`random_state=42`), así que los ids de cluster son
estables y la curaduría es reproducible.

### 5. Grafo con física mínima, sembrado por UMAP

El grafo usa `vis-network` con fuerza dirigida, pero las posiciones iniciales
vienen de UMAP, así que la estructura semántica ya está antes de simular nada. La
física es intencionalmente débil (velocidad máxima 0.3, amortiguación alta) para
que los nodos "respiren" un poco sin desordenarse, y se **apaga al pasar el cursor
o arrastrar** — así arrastrar mueve solo el nodo tomado y clicar es fácil. Este es
un criterio de usabilidad, no estético: un grafo que se mueve mucho es imposible de
usar.

### 6. El chat es RAG, no un modelo suelto

Tlamatini no "sabe" de leyes; **recupera y cita**. En cada pregunta:

1. Se embebe la pregunta y se buscan los 12 fragmentos más cercanos en FAISS.
2. Se expanden las leyes involucradas con sus relaciones del grafo (materia, leyes
   que citan, instituciones, abrogaciones).
3. Se arma un prompt con el **texto de las leyes** primero y las relaciones después,
   y se pide responder sobre el contenido citando ley y artículo, sin inventar.

Devuelve, además de la respuesta, la lista de leyes usadas como contexto, para que
el frontend las vuelva enlaces al lector. Modelo: `deepseek-v4-flash` (el tier
rápido y barato; configurable con `DS_MODEL`). Se ofrece información general, no
asesoría legal, y así se declara en la interfaz.

### 7. Búsqueda semántica

`sentence-transformers` con `paraphrase-multilingual-MiniLM-L12-v2` (384 dims,
entrenado para español), FAISS con producto interno sobre vectores normalizados
(equivale a coseno). Los textos se parten en fragmentos de 500 palabras con 50 de
traslape. El buscador colapsa los fragmentos a un resultado por documento y filtra
por similitud mínima 0.3.

### 8. Grafo de conocimiento por coincidencia verbatim

Las citas ley→ley se detectan buscando el nombre normalizado completo de cada ley
dentro del texto de las demás — verbatim, alta precisión, sin falsos positivos por
sinónimos. La Constitución se maneja aparte porque se cita en forma corta. Las
instituciones se extraen por regex y se filtran los "hubs" que aparecen en
demasiadas leyes (texto de formulario). Las abrogaciones se detectan en el texto
transitorio.

### 9. Local-first, una dependencia externa

Todo el índice, el grafo y el texto viven en `web/` como archivos. El servidor los
carga en memoria al arrancar. No hay base de datos ni servicios en la nube. La
única llamada externa es a DeepSeek, y solo para el chat: sin API key, el mapa, la
búsqueda y el lector funcionan igual.

---

## Endpoints

| Ruta | Qué hace |
|---|---|
| `GET /api/search?q=&k=` | Búsqueda semántica; lista rankeada de fragmentos |
| `POST /api/chat` | Respuesta RAG + leyes de contexto |
| `GET /api/graph/map` | Mapa plano: leyes coloreadas por rama + aristas de cita |
| `GET /api/clusters` | Leyenda de ramas (id → nombre, color, tamaño) |
| `GET /api/law/<nombre>` | Ficha: materia, citas, instituciones, abrogaciones |
| `GET /api/text/<nombre>` | Texto completo limpio de la ley |
| `GET /api/graph` | Grafo completo (leyes + instituciones) |

---

## Correr el proyecto

```bash
pip install -r requirements.txt

# La API key de DeepSeek va en .env (opcional; solo para el chat).
# .env está en .gitignore: nunca la subas al repositorio.
cp .env.example .env    # y edita DS_TOKEN

python3 server.py          # http://localhost:8765
```

### Regenerar los datos

Solo si cambian las leyes de origen. Los índices ya construidos vienen en `web/`;
el corpus crudo (`datos/`, 300+ MB) no se versiona: descárgalo del dataset
publicado en *Data* (MDPI, 2022) <https://www.mdpi.com/2306-5729/7/7/91> y colócalo
en `datos/`. El orden importa:

```bash
python3 build_topics.py     # materias (metadato)
python3 build_rag.py        # índice vectorial (re-embebe ~14k fragmentos, tarda minutos)
python3 build_clusters.py   # ramas semánticas (UMAP + HDBSCAN)  [usa DS_TOKEN para nombrar]
python3 build_kg.py         # grafo de citas/instituciones
```

---

## Dependencias

`flask`, `faiss-cpu`, `sentence-transformers`, `umap-learn`, `hdbscan`,
`scikit-learn`, `numpy`, `requests`, `python-dotenv`. El frontend carga
`vis-network` por CDN; sin build step, sin framework.

## Límites conocidos

- Cobertura: ~313 leyes federales vigentes, no reglamentos ni normatividad estatal.
- El texto viene de extracción de PDF; se limpió lo detectable, pero puede quedar
  ruido de formato en tablas y fórmulas.
- El chat es de recuperación: si el fragmento relevante no entra en el contexto, lo
  dice en vez de inventar, pero eso significa que no cubre toda la ley en una sola
  respuesta.
- No es asesoría legal.
