# API de Extracción RPA

Solución para prueba técnica que controla un **bot Selenium** para iniciar sesión en un portal web, aplicar filtros de rango de fechas, extraer filas de facturas y persistirlas en **PostgreSQL** — todo orquestado mediante una API REST en **FastAPI** y empaquetado con **Docker Compose**.

---

## Tabla de contenidos

1. [Descripción general](#descripción-general)
2. [Arquitectura](#arquitectura)
3. [Estructura del proyecto](#estructura-del-proyecto)
4. [Cómo ejecutar](#cómo-ejecutar)
5. [Variables de entorno](#variables-de-entorno)
6. [Endpoints de la API](#endpoints-de-la-api)
7. [Decisiones técnicas](#decisiones-técnicas)
8. [Limitaciones](#limitaciones)
9. [Qué se mejoraría con más tiempo](#qué-se-mejoraría-con-más-tiempo)

---

## Descripción general

El sistema expone cinco endpoints HTTP. Un cliente hace `POST` con un rango de fechas y un límite de filas; la API crea inmediatamente un registro **Job**, lanza el bot Selenium en un hilo en segundo plano y devuelve un `job_id`. El cliente consulta `GET /jobs/{id}` hasta que el job llega a `success` o `failed`, y luego obtiene las filas extraídas mediante `GET /records?job_id=…`.

El bot inicia sesión en el portal, navega a **Facturación → Generar Factura**, aplica los filtros de fecha, hace clic en **Buscar**, espera a que la tabla de resultados se actualice y extrae hasta `limit_requested` filas. Cada fila extraída se almacena como un `Record` vinculado al `Job` padre.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                       Cliente HTTP                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI  (async)                              │
│                                                                 │
│  POST /rpa/extract ──► job_service.create_job()                 │
│                    └──► loop.run_in_executor(thread_pool, bot)  │
│                                                                 │
│  GET  /jobs           ──► job_service.list_jobs()               │
│  GET  /jobs/{id}      ──► job_service.get_job()                 │
│  GET  /records        ──► record_service.list_records()         │
│  GET  /records/{id}   ──► record_service.get_record()           │
└───────────┬───────────────────────────┬─────────────────────────┘
            │ asyncpg (async)           │ ThreadPoolExecutor
            ▼                           ▼
┌───────────────────┐       ┌───────────────────────────────────┐
│    PostgreSQL     │◄──────│         Bot RPA  (sync)           │
│                   │       │                                   │
│  tabla jobs       │       │  driver_factory  → Chrome remoto  │
│  tabla records    │       │  login           → autenticación  │
└───────────────────┘       │  navigation      → menú           │
                            │  filters         → filtros fecha  │
                            │  extractor       → filas tabla    │
                            └───────────────────────────────────┘
                                              │
                                              ▼
                            ┌───────────────────────────────────┐
                            │  selenium/standalone-chrome       │
                            │  (Docker, puerto 4444)            │
                            │  Visor VNC en puerto 7900         │
                            └───────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Frontend React  (Nginx, puerto 3001)                           │
│  Consume la API en http://localhost:8004                        │
└─────────────────────────────────────────────────────────────────┘
```

### Responsabilidades de cada componente

| Componente | Archivo(s) | Responsabilidad |
|------------|-----------|-----------------|
| Rutas de la API | `app/api/routes/` | Validación de entrada, respuestas HTTP, despacho |
| Servicio de jobs | `app/services/job_service.py` | CRUD de jobs y transiciones de estado |
| Servicio de records | `app/services/record_service.py` | Persistencia y consultas de registros |
| Orquestador del bot | `app/rpa/bot.py` | Ciclo de vida del job, manejo de errores, escrituras en DB desde el hilo |
| Fábrica de driver | `app/rpa/driver_factory.py` | Creación del WebDriver remoto con reintentos |
| Login | `app/rpa/login.py` | Flujo de autenticación en el portal |
| Navegación | `app/rpa/navigation.py` | Navegación por el menú hasta Generar Factura |
| Filtros | `app/rpa/filters.py` | Entradas de fecha + Buscar + detección de resultados |
| Extractor | `app/rpa/extractor.py` | Parseo de filas de la tabla |
| Selectores | `app/rpa/selectors.py` | Todos los localizadores DOM en un solo lugar |
| Configuración | `app/core/config.py` | pydantic-settings, lee `.env` |
| Logging | `app/core/logging.py` | Salida JSON con structlog |

---

## Estructura del proyecto

```
BotSelenium/
├── app/
│   ├── main.py                  # Fábrica de la app FastAPI + endpoint /health
│   ├── api/
│   │   ├── deps.py              # Dependencia de sesión async de DB
│   │   └── routes/
│   │       ├── rpa.py           # POST /rpa/extract
│   │       ├── jobs.py          # GET /jobs, GET /jobs/{id}
│   │       └── records.py       # GET /records, GET /records/{id}
│   ├── core/
│   │   ├── config.py            # Settings mediante pydantic-settings
│   │   └── logging.py           # Logger JSON con structlog
│   ├── db/
│   │   ├── base.py              # DeclarativeBase de SQLAlchemy
│   │   ├── session.py           # Motor async + fábrica de sesiones
│   │   └── models/
│   │       ├── job.py           # Modelo ORM Job
│   │       └── record.py        # Modelo ORM Record
│   ├── schemas/
│   │   ├── job.py               # Modelos Pydantic de request / response
│   │   └── record.py
│   ├── services/
│   │   ├── job_service.py       # Lógica de negocio de jobs
│   │   └── record_service.py    # Lógica de negocio de records
│   └── rpa/
│       ├── selectors.py         # Todos los localizadores DOM (centralizados, todos TODO)
│       ├── driver_factory.py    # Constructor del WebDriver remoto
│       ├── login.py             # Flujo de login con esperas explícitas
│       ├── navigation.py        # Navegación por el menú
│       ├── filters.py           # Filtros de fecha + Buscar + polling de resultados
│       ├── extractor.py         # Extracción de filas de la tabla
│       └── bot.py               # Orquestador (punto de entrada del ThreadPoolExecutor)
├── migrations/                  # Scripts de migración Alembic
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
├── tests/
│   ├── conftest.py              # Fixtures SQLite + AsyncClient
│   ├── test_bot.py              # Pruebas unitarias de orquestación del bot
│   └── test_api/
│       ├── test_rpa.py
│       ├── test_jobs.py
│       └── test_records.py
│   └── test_rpa/
│       └── test_extraction.py
├── .github/
│   └── workflows/
│       └── ci.yml               # Pipeline: lint → test → docker-build
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .dockerignore
├── alembic.ini
├── requirements.txt
├── pytest.ini
└── ruff.toml
```

---

## Cómo ejecutar

### Requisitos previos

- Docker Engine 24+ y Docker Compose v2
- Python 3.12+ *(solo para desarrollo local)*

### 1. Configurar el entorno

```bash
cp .env.example .env
```

Abre `.env` y completa cada valor marcado con `<REPLACE>`:

```
POSTGRES_PASSWORD=<REPLACE>
PORTAL_URL=<REPLACE>
PORTAL_USERNAME=<REPLACE>
PORTAL_PASSWORD=<REPLACE>
```

### 2. Levantar el stack completo

```bash
docker compose up --build
```

Docker Compose inicia cuatro contenedores en orden de dependencia:

| Contenedor | Imagen | Puerto local | Healthcheck | Listo cuando… |
|------------|--------|:------------:|-------------|---------------|
| `db` | `postgres:16-alpine` | `5433` | `pg_isready` | Postgres acepta conexiones |
| `selenium` | `selenium/standalone-chrome:latest` | `4444`, `7900` (VNC) | `curl /wd/hub/status` | Chrome Grid reporta `ready` |
| `api` | imagen local `Dockerfile` | `8004` | `curl /health` | Alembic aplicó las migraciones y uvicorn está escuchando |
| `frontend` | imagen local `frontend/Dockerfile` | `3001` | — | Nginx sirve la SPA React |

> **Nota de plataforma:** la imagen de Selenium es `selenium/standalone-chrome` (x86\_64 / Windows / Linux amd64).

URLs disponibles una vez que el stack está en pie:

| Interfaz | URL |
|----------|-----|
| API REST (Swagger) | <http://localhost:8004/docs> |
| Frontend React | <http://localhost:3001> |
| Selenium Grid UI | <http://localhost:4444/ui> |
| VNC (ver el bot en vivo) | <http://localhost:7900> (contraseña: `secret`) |
| PostgreSQL (externo) | `localhost:5433` |

### 3. Disparar un job de extracción

```bash
curl -s -X POST http://localhost:8004/rpa/extract \
  -H "Content-Type: application/json" \
  -d '{
    "fecha_inicial": "2024-01-01",
    "fecha_final":   "2024-01-31",
    "limit_requested": 50
  }'
```

Respuesta `202 Accepted`:

```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending"
}
```

### 4. Consultar el estado del job

```bash
curl -s http://localhost:8004/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6 | python3 -m json.tool
```

Valores posibles de `status`: `pending` → `running` → `success` | `failed`

### 5. Obtener los registros extraídos

```bash
# Todos los registros de un job, paginados
curl -s "http://localhost:8004/records?job_id=3fa85f64-5717-4562-b3fc-2c963f66afa6&page=1&size=20"

# Un registro individual
curl -s "http://localhost:8004/records/<record_id>"
```

### Desarrollo local (sin Docker)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Iniciar solo DB y Selenium con Docker
docker compose up db selenium -d

# Aplicar migraciones
alembic upgrade head

# Ejecutar la API con recarga automática
uvicorn app.main:app --reload
```

### Ejecutar pruebas

```bash
pip install aiosqlite          # driver async de SQLite para la DB en memoria
pytest tests/ -v
```

Las pruebas utilizan **SQLite en memoria** y mockean todas las llamadas a Selenium y al navegador — no se requieren servicios en ejecución.

### Depuración visual (VNC de Selenium)

Establece `SELENIUM_HEADLESS=false` en `.env`, luego abre <http://localhost:7900> (contraseña: `secret`) para ver la sesión de Chrome en vivo mientras el bot se ejecuta.

### Migraciones de base de datos

```bash
# Aplicar todas las migraciones pendientes
alembic upgrade head

# Generar una nueva migración tras cambios en los modelos
alembic revision --autogenerate -m "descripción breve"

# Revertir un paso
alembic downgrade -1
```

---

## Variables de entorno

Todas las variables son leídas por `app/core/config.py` mediante **pydantic-settings**.  
Defínelas en `.env` (ver `.env.example` para la plantilla completa con anotaciones).

| Variable | Requerida | Por defecto | Descripción |
|----------|:---------:|-------------|-------------|
| `POSTGRES_USER` | ✓ | — | Usuario de PostgreSQL |
| `POSTGRES_PASSWORD` | ✓ | — | Contraseña de PostgreSQL |
| `POSTGRES_DB` | ✓ | — | Nombre de la base de datos |
| `POSTGRES_HOST` | | `db` | Host — usar `db` dentro de Docker Compose |
| `POSTGRES_PORT` | | `5432` | Puerto de PostgreSQL |
| `PORTAL_URL` | ✓ | — | URL completa del portal web objetivo |
| `PORTAL_USERNAME` | ✓ | — | Usuario de login del portal |
| `PORTAL_PASSWORD` | ✓ | — | Contraseña de login del portal |
| `SELENIUM_REMOTE_URL` | | `http://selenium:4444/wd/hub` | Endpoint del Grid de Selenium |
| `SELENIUM_TIMEOUT_SECONDS` | | `30` | Segundos máximos para cada espera explícita |
| `SELENIUM_HEADLESS` | | `true` | Chrome sin interfaz gráfica; `false` habilita VNC |
| `RPA_MAX_WORKERS` | | `2` | Hilos del bot concurrentes (≤ SE_NODE_MAX_SESSIONS) |
| `LOG_LEVEL` | | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `APP_ENV` | | `development` | `development` habilita el echo logging de SQLAlchemy |

---

## Endpoints de la API

### `POST /rpa/extract`

Crea un Job e inicia el bot de extracción en segundo plano.  
Retorna inmediatamente — no espera a que el bot termine.

**Cuerpo de la solicitud**

```json
{
  "fecha_inicial":   "2024-01-01",
  "fecha_final":     "2024-01-31",
  "limit_requested": 50
}
```

Reglas de validación:
- `fecha_inicial` ≤ `fecha_final`
- `limit_requested` entre 1 y 10 000

**Respuesta** `202 Accepted`

```json
{ "job_id": "<uuid>", "status": "pending" }
```

---

### `GET /jobs`

Lista paginada de todos los jobs.

| Parámetro | Tipo | Por defecto | Descripción |
|-----------|------|-------------|-------------|
| `status` | enum | — | Filtrar por `pending` / `running` / `success` / `failed` |
| `page` | int | `1` | Número de página (base 1) |
| `size` | int | `20` | Resultados por página (máx. 100) |

**Respuesta** `200 OK`

```json
{
  "total": 5,
  "page":  1,
  "size":  20,
  "items": [
    {
      "id":              "<uuid>",
      "status":          "success",
      "fecha_inicial":   "2024-01-01",
      "fecha_final":     "2024-01-31",
      "limit_requested": 50,
      "total_extracted": 42,
      "created_at":      "2024-01-31T10:00:00Z"
    }
  ]
}
```

---

### `GET /jobs/{job_id}`

Detalle completo de un job, incluyendo información de error.

**Respuesta** `200 OK` / `404 Not Found`

```json
{
  "id":              "<uuid>",
  "status":          "failed",
  "fecha_inicial":   "2024-01-01",
  "fecha_final":     "2024-01-31",
  "limit_requested": 50,
  "total_extracted": null,
  "error_message":   "LoginError: Login timed out at https://portal/login",
  "created_at":      "2024-01-31T10:00:00Z",
  "started_at":      "2024-01-31T10:00:02Z",
  "finished_at":     "2024-01-31T10:00:32Z"
}
```

---

### `GET /records`

Lista paginada de registros extraídos, opcionalmente filtrada por job.

| Parámetro | Tipo | Por defecto | Descripción |
|-----------|------|-------------|-------------|
| `job_id` | uuid | — | Retornar solo los registros de este job |
| `page` | int | `1` | Número de página |
| `size` | int | `20` | Resultados por página (máx. 100) |

---

### `GET /records/{record_id}`

Detalle completo de un registro, incluyendo `raw_row_json`.

**Respuesta** `200 OK` / `404 Not Found`

```json
{
  "id":                          "<uuid>",
  "job_id":                      "<uuid>",
  "external_row_id":             "INV-001",
  "patient_name":                "Ana García",
  "patient_document":            "12345678",
  "date_service_or_facturation": "2024-01-15",
  "site":                        "Clínica Norte",
  "contract":                    "Plan Salud A",
  "raw_row_json":                { "col_0": "INV-001", "col_1": "Ana García", "..." : "..." },
  "captured_at":                 "2024-01-31T10:00:10Z"
}
```

---

### `GET /health`

Verificación de liveness utilizada por Docker Compose y balanceadores de carga.

**Respuesta** `200 OK`

```json
{ "status": "ok", "version": "1.0.0" }
```

---

## Decisiones técnicas

### API async + Selenium sync mediante ThreadPoolExecutor

FastAPI es completamente `async` — todas las rutas y operaciones de DB usan `await`. Selenium es inherentemente síncrono y no puede ser esperado con `await`. En lugar de agregar una cola de tareas (Celery + Redis), el bot corre en un `ThreadPoolExecutor` acotado almacenado en `app.state`:

```
ruta → asyncio.get_running_loop().run_in_executor(thread_pool, run_extraction_job, ...)
```

Cada hilo del bot crea su propio event loop de `asyncio` para las escrituras async en la DB. Esto mantiene el event loop de FastAPI libre para atender otras solicitudes mientras el bot se ejecuta.

El pool de hilos está acotado mediante `RPA_MAX_WORKERS` para no agotar el límite de sesiones del Grid de Selenium.

**Trade-off:** para más de unos pocos jobs concurrentes, Celery + Redis sería más apropiado. Se eligió `ThreadPoolExecutor` para evitar agregar un broker como dependencia de infraestructura en el contexto de una prueba técnica.

### JSONB `raw_row_json` + columnas tipadas con nombre

El esquema de la tabla del portal es desconocido hasta que se inspecciona el DOM. Se usan dos capas de almacenamiento:

- **`raw_row_json` (JSONB)** — siempre escrito; almacena la fila completa textualmente independientemente de si las columnas con nombre están mapeadas. Funciona como trazabilidad y fuente para reprocesamiento.
- **Columnas tipadas** (`patient_name`, `patient_document`, etc.) — se poblan una vez que `selectors.py → ColumnIndex` es completado tras inspeccionar el DOM. Las columnas con nombre hacen que las consultas `WHERE patient_document = 'X'` sean naturales sin operadores `JSONB`.

Hasta que los selectores sean verificados, las columnas con nombre son `NULL` y todos los datos están disponibles en `raw_row_json`.

### Selectores centralizados (`selectors.py`)

Cada localizador DOM está definido como una constante nombrada en `app/rpa/selectors.py`, agrupada por contexto de página (`LoginPage`, `MainNav`, `FilterForm`, `ResultTable`, `ColumnIndex`). Ningún otro archivo contiene una cadena de localizador. Esto significa que actualizar un selector tras inspeccionar el DOM requiere cambiar exactamente una línea en un solo archivo.

### Logging JSON estructurado con structlog

Cada entrada de log es un objeto JSON con campos `job_id`, `step` y `timestamp`. Esto hace trivial la agregación de logs (Datadog, Loki, CloudWatch) — sin necesidad de parsear texto. Cada hilo del bot vincula `job_id` al contexto de su logger al inicio de `run_extraction_job`, por lo que cada llamada de log posterior lleva el ID del job automáticamente.

### Solo esperas explícitas

`driver.implicitly_wait(0)` se configura en cada instancia de WebDriver. Toda la sincronización utiliza `WebDriverWait` + `expected_conditions`. Mezclar esperas implícitas y explícitas causa condiciones de carrera impredecibles en Selenium — esta regla las previene.

### pydantic-settings para configuración

Todas las variables de entorno están declaradas como campos tipados en `app/core/config.py`. El `database_url` se construye a partir de sus partes (`POSTGRES_HOST`, `POSTGRES_PORT`, etc.) en lugar de aceptarse como una cadena única opaca. Esto previene inyección en la cadena de conexión y hace cada variable individualmente sobreescribible en Docker Compose.

### `JobNotFoundError` separado del camino 404 de la API

`job_service.get_job()` retorna `None` (usado por las rutas de la API para el manejo de 404). Las funciones de mutación (`mark_job_running`, `mark_job_success`, `mark_job_failed`) usan un helper interno `_get_job_or_raise()` que lanza `JobNotFoundError` si la fila no existe. Esto evita que el bot tenga éxito silenciosamente cuando la fila del job fue eliminada, dejando records huérfanos y el job estancado en `pending`.

---

## Limitaciones

**Los selectores DOM son marcadores de posición.** Cada localizador en `app/rpa/selectors.py` está marcado con `# TODO: verify` y fue escrito desde patrones comunes de portales sin inspeccionar el DOM real. El bot no ejecutará de extremo a extremo hasta que estos sean confirmados y `ColumnIndex` esté completo.

**Sin autenticación en la API.** Los cinco endpoints son públicamente accesibles. No existe mecanismo de API key, OAuth ni sesión. Cualquier persona con acceso a la red puede disparar un job del bot.

**Extracción de una sola página.** El bot extrae las filas visibles en la primera página de resultados. Si el portal pagina sus resultados, las filas más allá de la primera página no se recolectan independientemente del valor de `limit_requested`.

**Sin cancelación de jobs.** Una vez que un job está en `running`, no existe mecanismo de API para detenerlo. La sesión del navegador se ejecuta hasta completarse (o hasta el timeout).

**Sin reintentos para jobs fallidos.** Un job que llega a `failed` permanece fallido. Una nueva extracción requiere un nuevo `POST /rpa/extract`.

**Sin limitación de velocidad ni cola de jobs.** Un cliente puede enviar arbitrariamente muchos jobs concurrentes. El `ThreadPoolExecutor` limita los hilos del bot activos, pero los jobs enviados se encolan en memoria sin persistencia — un reinicio pierde los jobs en cola (aún no en ejecución).

**Medidas anti-bot del portal no manejadas.** Si el portal implementa CAPTCHA, limitación de velocidad por IP o detección de comportamiento, el bot fallará en el login o durante la navegación. Estos casos aparecen como `LoginError` o `NavigationError` en el `error_message` del job.

---

## Qué se mejoraría con más tiempo

**1. Verificar e implementar los selectores DOM.**  
La prioridad más alta. Con acceso al portal, inspeccionar el DOM toma entre 30 y 60 minutos. Una vez actualizado `selectors.py` y completados los valores de `ColumnIndex`, el bot es funcional de extremo a extremo.

**2. Soporte de paginación en el portal.**  
Luego de `Buscar`, detectar si los resultados abarcan múltiples páginas (un control de "siguiente página"), iterar y detenerse cuando se alcance `limit_requested` o se agoten los resultados.

**3. Autenticación de la API.**  
Agregar un header de API key (`X-API-Key`) validado contra un secreto hasheado almacenado en la configuración del entorno. La dependencia `Security` de FastAPI convierte esto en un único interceptor.

**4. Reemplazar ThreadPoolExecutor con Celery + Redis.**  
Para cargas de trabajo en producción con muchos usuarios concurrentes, Celery provee colas de tareas durables (sobrevive reinicios), limitación de velocidad, reintento de tareas con backoff exponencial y una interfaz web (Flower) para monitoreo.

**5. Mecanismo de reintentos para jobs.**  
Agregar un campo `retry_count` a `Job` y un endpoint `POST /jobs/{id}/retry`. El bot podría reintentar automáticamente fallas transitorias (timeouts de red, problemas del portal) hasta un máximo configurable.

**6. Cancelación de jobs.**  
Agregar `POST /jobs/{id}/cancel` que establezca una flag de cancelación thread-safe verificada entre los pasos del RPA. Requiere un pequeño mecanismo de coordinación (por ejemplo, un `threading.Event` compartido indexado por `job_id`).

**7. Monitoreo y observabilidad.**  
Exponer métricas Prometheus (jobs activos, tasa de éxito/fallo, duración de la extracción) mediante `/metrics`. Agregar Sentry para seguimiento de excepciones con contexto completo (ID del job, paso, URL del portal).

**8. Suite de pruebas de integración.**  
Agregar una prueba que levante un portal mock local (una aplicación Flask simple sirviendo HTML estático con estructura de tabla conocida), ejecute el bot completo contra él y verifique que los registros se persisten correctamente. Esto permitiría que el CI detecte regresiones en los selectores automáticamente.

**9. Gestión de secretos.**  
Reemplazar las variables de entorno para `PORTAL_PASSWORD` y `POSTGRES_PASSWORD` con un gestor de secretos (AWS Secrets Manager, HashiCorp Vault o Docker Secrets) para que las credenciales nunca se almacenen en archivos `.env` ni en el historial del shell.

**10. Soporte para múltiples portales.**  
Parametrizar los selectores para que distintas configuraciones de portal puedan almacenarse en la base de datos y seleccionarse al crear el job, permitiendo que la misma infraestructura de bot sirva a múltiples portales.
