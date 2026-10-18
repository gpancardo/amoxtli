# Amoxtli — Pitch (15 minutos)

> Guion para presentar Amoxtli como producto. Técnicamente ligero pero honesto:
> nada que no haga hoy. Los tiempos son sugeridos.

---

## En una frase

Amoxtli convierte la maraña de la legislación federal mexicana en algo que se puede
ver, buscar por significado y leer en su texto real — con un asistente que responde
citando la ley, no inventándola.

---

## 1. El problema (2 min)

La legislación federal vigente son cientos de leyes que se citan, se reforman y se
abrogan entre sí. Para cualquiera —incluido quien estudió derecho— responder tres
preguntas básicas cuesta trabajo desproporcionado:

- **¿Qué leyes tratan este tema?** No hay un mapa; hay listados alfabéticos.
- **¿Cómo se relaciona esta ley con las demás?** Las citas están enterradas en el
  articulado.
- **¿Qué dice exactamente sobre X?** El texto oficial está en PDF, mal formateado,
  y buscar por palabra exacta falla cuando no sabes el término legal preciso.

Las herramientas actuales son buscadores de texto plano sobre PDF. Funcionan si ya
sabes qué buscar y cómo se llama. No ayudan a *descubrir* ni a *entender la
estructura*.

## 2. Qué es Amoxtli (1 min)

Tres vistas sobre el mismo cuerpo de ~313 leyes federales:

1. **Mapa**: cada ley es un punto, agrupado por cercanía temática y conectado a las
   leyes que cita. Ves el territorio, no una lista.
2. **Búsqueda por significado**: describes lo que buscas en lenguaje natural y
   encuentra los documentos relevantes aunque no uses el término técnico.
3. **Lector + asistente**: abres el texto real y limpio de la ley, y puedes
   preguntarle a un asistente que responde citando ese texto.

## 3. Demo (5 min) — el corazón del pitch

Recorrido en vivo, sin diapositivas:

1. **Abrir el mapa.** "Esto son las ~313 leyes federales. El color es la rama
   temática, y no la puso alguien a mano: sale de agrupar las leyes por cómo se
   parecen sus textos. Paso el cursor y me dice la ley y su materia."
2. **Buscar algo cotidiano**, p. ej. *"qué pasa si me despiden sin causa"*. "No
   escribí 'Ley Federal del Trabajo' ni 'indemnización constitucional'. Aun así me
   trae los documentos correctos, ordenados por relevancia."
3. **Abrir un resultado.** "Este es el texto real de la ley, limpio —sin las letras
   cortadas del PDF original— y me lleva directo al pasaje que buscaba. La URL es
   compartible: puedo mandarla."
4. **Preguntar al asistente** sobre el contenido. "Le pregunto qué dice tal ley
   sobre tal cosa. Responde citando el artículo, y —esto es lo importante— cada ley
   que menciona es un enlace al texto para verificarlo. Si el texto no alcanza para
   responder, lo dice en vez de inventar."
5. **Clic en una ley del panel** que cita otra → saltar entre leyes relacionadas.
   "Así se navega la estructura: de una ley a las que cita, sin salir del sistema."

## 4. Valor real por audiencia (4 min)

Honesto: cada audiencia usa una capa distinta.

### Público en general
- **Qué gana**: entender qué dice una ley sin descifrar PDF ni jerga. Buscar en
  lenguaje normal y leer el texto oficial legible.
- **Ejemplo**: un trabajador, un contribuyente o un emprendedor que quiere saber
  "qué me aplica" empieza por una pregunta en español, no por el nombre de una ley.
- **Límite honesto**: es orientación e información, no asesoría legal. El asistente
  cita la ley; no sustituye a un abogado para un caso concreto.

### Estudiantes de derecho
- **Qué ganan**: el mapa hace visible la *estructura* del sistema jurídico —qué
  materias existen, qué leyes las componen, cómo se citan entre sí. Es una
  herramienta de estudio para ver el bosque, no solo el árbol.
- **Ejemplo**: preparar un tema cruzando las leyes de una materia y sus citas
  mutuas en minutos, con el texto a un clic.
- **Por qué es creíble**: las relaciones no son adivinadas; una cita aparece porque
  el nombre de una ley está literalmente en el texto de otra.

### Abogados
- **Qué ganan**: velocidad en la fase de exploración. Encontrar por significado las
  leyes aplicables, ver de un vistazo qué abroga o cita a qué, y saltar al articulado
  exacto. Un punto de partida rápido y verificable para el trabajo serio.
- **Ejemplo**: entrar a una materia poco frecuente y ubicar en minutos el cuerpo
  normativo relevante y sus conexiones, en lugar de reconstruirlo a mano.
- **Por qué confían**: todo es rastreable al texto oficial. El asistente no opina
  desde su "conocimiento": recupera pasajes reales y los cita; si no los tiene, lo
  admite.

## 5. Por qué funciona, sin humo (2 min)

- **El texto es real y está limpio.** Partimos de un dataset publicado de la
  legislación mexicana (revista *Data*, MDPI, 2022), con el texto completo del
  Diario Oficial —no resúmenes— y reparamos el daño de extracción de PDF (palabras
  cortadas, glifos basura).
- **La búsqueda entiende significado**, no solo palabras: usa embeddings
  multilingües en español, así que "me corrieron del trabajo" encuentra la ley
  laboral aunque no use ese término.
- **Los grupos temáticos emergen de los datos.** Agrupamos las leyes por la
  similitud real de su contenido, no por una taxonomía impuesta; luego etiquetamos
  esos grupos con los nombres de materia que usan los abogados.
- **El asistente está anclado.** Es recuperación-más-generación: solo habla de lo
  que recupera del texto, cita la fuente y reconoce cuando no sabe. Esa es la
  diferencia entre una herramienta jurídica usable y un chatbot que alucina.

## 6. Límites y honestidad (1 min)

- Cobertura actual: ~313 leyes federales vigentes. No reglamentos, no leyes
  estatales, no jurisprudencia — todavía.
- No es asesoría legal ni sustituye criterio profesional.
- El asistente responde con lo que cabe en el contexto recuperado; para un análisis
  exhaustivo de una ley larga, es punto de partida, no palabra final.

Decir esto no debilita el pitch: lo hace creíble. Una herramienta jurídica que
promete certeza total es la que no se debe usar.

## Cierre

Amoxtli no reemplaza al abogado ni a la ley: hace que la ley sea *encontrable,
navegable y legible*. Empieza donde hoy la gente se atora —"¿por dónde entro?"— y
la lleva, en pocos clics y siempre con la fuente a la vista, hasta el texto exacto.

Siguientes pasos naturales: ampliar cobertura (reglamentos, estatal), y versión
web pública. La base —texto limpio, búsqueda semántica, grafo verificable y
asistente anclado— ya está construida y funcionando.
