# Prueba Data Engineer SoccerSolver

Prototipo end to end que responde a la pregunta de negocio: ¿estamos pagando de más o de menos a un jugador comparado con el mercado?

El sistema obtiene y limpia datos de sueldos, los cruza con las valoraciones de mercado que aporta SoccerSolver, calcula un rango de sueldo esperado por similitud y lo muestra en una interfaz pensada para un director deportivo sin perfil técnico.

## Cómo ejecutarlo

```bash
pip install -r requirements.txt
python src/pipeline.py # descarga sueldos, limpia ambos datasets, escribe data/*.csv
python -m streamlit run app.py # UI
python -m pytest tests/ -q # tests
```

`python src/pipeline.py` es idempotente: se puede relanzar tantas veces como se quiera, cada vez sobreescribe `data/players_clean.csv` y `data/wages_clean.csv` de forma determinista (no hay append, no se duplica nada). Si el dataset de sueldos ya está en cache (`data_raw/wages_raw.csv`) no vuelve a llamar a la API; usa `--refresh` para forzar una redescarga.

Para volver a descargar de Kaggle hacen falta credenciales en `~/.kaggle/kaggle.json` (o las variables `KAGGLE_USERNAME` / `KAGGLE_KEY`). Si no hay credenciales, o Kaggle no responde, o el fichero remoto cambia de columnas, el pipeline no rompe: usa la cache local existente y avisa por stderr; si no hay ni cache ni acceso, falla con un mensaje explícito en vez de generar datos parciales silenciosamente.

## 1. Fuente de datos de sueldos

**Elegida:** [FIFA Player Data from Sofifa 2025-06-03](https://www.kaggle.com/datasets/aniss7/fifa-player-data-from-sofifa-2025-06-03) (Kaggle), scrape de sofifa.com de ~18.200 jugadores con valor de mercado y sueldo semanal reales según EA Sports FC 25, snapshot de junio 2025.

**Por qué esta y no otras:**
- *Datasets de sueldos "reales" tipo Capology* (prensa deportiva): más fieles a la realidad para las 5 grandes ligas, pero exigen scraping HTML frágil y **no cubren** las decenas de ligas secundarias/regionales que aparecen en `data.csv` (Championship, LaLiga2, Regionalliga, Serie D...). Habría dejado sin estimación a la mayoría de los ~19.500 jugadores del fichero de SoccerSolver.
- *Dataset de sueldos de GitHub/Kaggle "ultimus/football-wages-prediction" (temporada 2023-24)*: fue la primera opción explorada, pero solo cubre las 5 grandes ligas top y no trae `market_value` del mismo jugador, obligando a un cruce indirecto por percentiles entre dos poblaciones distintas (sin nombres, sin garantía de comparabilidad de escala).
- **La elegida** trae valor de mercado *y* sueldo del mismo jugador, lo que permite calibrar directamente la relación sueldo/valor en vez de aproximarla cruzando poblaciones distintas, y cubre de forma real hasta el tier 3-4 (Championship, League One, League Two, LaLiga2, 2. Bundesliga, 3. Liga, Serie B) en las 5 ligas de interés — mucho más solapamiento con `data.csv` que las alternativas de sueldos reales.

**Limitaciones de la fuente:**
- Es un dataset de un videojuego (EA Sports FC), no una nómina real: los valores/sueldos son estimaciones de EA calibradas contra el mercado, no cifras oficiales de club. Se trata como la mejor aproximación abierta disponible, no como dato contable.
- Snapshot único de junio 2025: no captura la ventana de fichajes de verano 2025 ni revalorizaciones posteriores.
- No cubre las ligas de tier 4-5 de `data.csv` (Regionalliga, Serie D, Segunda/Primera Federación, Primavera): para esos jugadores el pipeline usa como aproximación el sueldo real del tier disponible más cercano (ver algoritmo), marcando la confianza como media/baja.
- Sueldo publicado como semanal (convención sofifa); se anualiza (×52) para comparar con `market_value`, que es un valor puntual, no recurrente.

## 2. Decisiones de limpieza

**`data_raw/data.csv` (SoccerSolver) → `data/players_clean.csv`:**
- Se descartan filas sin `market_value`, sin `birth_date` o sin `position`: sin estos tres campos no se puede ubicar al jugador en el baremo. (2.737 de 19.476 filas, sobre todo por `market_value` ausente — jugadores sin valoración de mercado activa.)
- `age` se deriva de `birth_date` a fecha de ejecución del pipeline.
- Se descartan valores de `market_value` o `age` fuera de rango razonable (edad 14-45, valor 1.000€-300M€) como salvaguarda ante datos corruptos.
- Se deduplica por `player_id` (se han encontrado 120 duplicados, probablemente jugadores cedidos con doble registro club origen/destino); se conserva la primera aparición.
- Se añade `tier` (nivel competitivo 1-5) por competición, ver `src/tiers.py`.

**Dataset de sueldos → `data/wages_clean.csv`:**
- `value`/`wage` (texto tipo `"€115.5M"`) se parsean a euros; filas no parseables se descartan.
- `wage` semanal se anualiza (×52).
- `positions` (multi-posición tipo `"CDM,CM"`) se reduce a la primera posición y se mapea al esquema de 4 posiciones de SoccerSolver (GK/DEF/MID/ATT).
- Se descartan filas sin liga, posición mapeable, sueldo o valor, y las que caen fuera de rango (mismos límites que arriba). Se deduplica por (nombre, club, edad, sueldo, valor).

En ambos casos el pipeline registra cuántas filas se descartan y por qué motivo (ver métricas impresas por `pipeline.py`), en vez de fallar silenciosamente o mezclar datos inválidos.

## 3. Algoritmo de comparación (baremo)

Ver `src/comparator.py`. Como los dos datasets no comparten jugadores (el de sueldos no tiene `player_id` de SoccerSolver), no se puede hacer un `merge` directo. En su lugar:

1. Se construye un grupo de comparables del dataset de sueldos con **misma posición** y **mismo tier de liga**, y **edad similar** (ventana ±4 años, que se ensancha hasta ±12 si hay menos de 8 comparables).
2. Se calcula la distribución del ratio `sueldo_anual / valor_mercado` dentro de ese grupo.
3. El rango esperado = `market_value` del jugador objetivo × percentiles 25/50/75 de esa distribución de ratios. Se transporta el *ratio* entre datasets, no el sueldo absoluto, porque son poblaciones distintas de jugadores y solo el ratio es comparable entre ellas.
4. Si el tier del jugador no tiene comparables reales (tiers 4-5), se usa el ratio del tier real disponible más cercano, y la confianza baja en consecuencia.

**Variables usadas y por qué:** posición (determinante del rol y de la escala salarial), tier de liga (el mismo valor de mercado se paga muy distinto en Premier League que en Regionalliga), edad (curva de sueldos no lineal: pico en torno a 26-29). Se descartó usar la posición detallada (`main_position`, 15+ valores) porque fragmenta demasiado la muestra sin aportar mejor señal que la posición macro para este prototipo.

**Casos con pocos comparables:** ventana de edad adaptativa (punto 1) + fallback de tier (punto 4) + una etiqueta de confianza (Alta/Media/Baja) que combina tamaño de muestra, si se ha necesitado ensanchar la ventana de edad, y si se ha tenido que aproximar con un tier distinto al real. Los tiers 3+ nunca llegan a "Alta" aunque haya muchos comparables, porque el dato real de esos tiers solo existe para alguna liga concreta (p.ej. League Two inglesa) aplicada como aproximación a ligas equivalentes de otros países — una fuente de incertidumbre que el tamaño de muestra no refleja.

**Comunicación de incertidumbre:** el resultado no es un número único sino un rango (p25-mediana-p75) más una etiqueta de confianza y el listado de comparables usados, para que el director deportivo vea con qué se ha comparado y pueda juzgar la fiabilidad él mismo, no solo confiar en una cifra.

## 4. Interfaz

`streamlit run app.py`: buscador de jugador, ficha (posición/edad/valor de mercado/liga), rango de sueldo esperado (mínimo/esperado/máximo), confianza con semáforo, y tabla de comparables usados.

## Qué haría distinto con más tiempo/datos reales

- Sustituir el dataset de videojuego por sueldos reportados por prensa (Capology y similares) para las 5 grandes ligas, y reservar el dataset actual solo como fallback para ligas sin cobertura de prensa.
- Contrastar `market_value` de SoccerSolver con el `value` del dataset de sueldos para los jugadores que coinciden por nombre, como validación cruzada de que ambas fuentes miden algo comparable.
- Modelo de ratio sueldo/valor por posición+tier+edad más fino (regresión en vez de percentiles por grupo), una vez haya suficiente dato real para no sobreajustar.
- Persistir las salidas de `pipeline.py` con versión/fecha (en vez de sobreescribir) para poder auditar cómo cambia la estimación entre ejecuciones.
