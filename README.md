# 📚 TelegramMediaBot

> Bot de Telegram para descarga y envío de libros, música (MP3), videos (MP4) y contenido compatible con dispositivos Apple (iPod/iTunes).

---

## 🧩 Tabla de Contenidos

- [Descripción](#descripción)
- [Características](#características)
- [Tecnologías](#tecnologías)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Requisitos Previos](#requisitos-previos)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Uso del Bot](#uso-del-bot)
- [Docker Compose](#docker-compose)
- [Comandos Disponibles](#comandos-disponibles)
- [Libros: fuentes y descargas](#-libros-fuentes-y-descargas)
- [Pruebas](#-pruebas)
- [Contribuir al Repositorio](#contribuir-al-repositorio)
- [Roadmap](#roadmap)
- [Licencia](#licencia)

---

## 📖 Descripción

**TelegramMediaBot** es un bot desarrollado en Python que permite a los usuarios solicitar y recibir directamente en Telegram:

- 📕 Libros en formatos PDF, EPUB y MOBI
- 🎵 Audio en formato MP3 y M4A (compatible con iPod/Apple Music)
- 🎬 Videos en formato MP4 y MOV
- 🎧 Podcasts y audiolibros en formato AAC / M4B (Apple)

El bot descarga el contenido solicitado, lo convierte si es necesario al formato requerido y lo envía directamente al chat del usuario en Telegram.
Además, incluye un worker en segundo plano que monitoriza la carpeta de entrada y procesa archivos PDF/EPUB.

---

## ✨ Características

- Búsqueda de libros por título o autor en 6 fuentes, con respaldo automático en paralelo y cambio de fuente con un botón
- Descarga y envío de archivos multimedia (MP3, MP4, M4A, AAC, MOV)
- Conversión de formatos de audio para compatibilidad con dispositivos Apple
- Sistema de búsqueda con resultados paginados (la lista se conserva para descargar varios libros)
- Soporte para múltiples usuarios simultáneos
- Límite configurable de tamaño de archivo
- Registro de actividad (logs) por usuario
- Modo administrador con estadísticas de uso
- **NUEVO:** Soporte para descarga de Listas de Reproducción (Playlists)
- **NUEVO:** Incrustación automática de carátulas y metadatos en archivos multimedia

---

## 🛠 Tecnologías

| Herramienta | Uso |
|---|---|
| Python 3.11+ (Docker/CI: 3.12) | Lenguaje principal |
| [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) | Interfaz con la API de Telegram |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Descarga de audio y video |
| [FFmpeg](https://ffmpeg.org/) | Conversión de formatos multimedia |
| [Calibre CLI](https://calibre-ebook.com/) | Conversión de formatos de libros |
| [aiohttp](https://docs.aiohttp.org/) | Peticiones HTTP asíncronas |
| dotenv | Manejo de variables de entorno |
| [watchdog](https://github.com/gorakhargosh/watchdog) | Monitorización de carpetas en tiempo real |

---

## 📁 Estructura del Proyecto

```
Chatbot/
├── bot/
│   ├── main.py                 # Arranque: sesión HTTP, comandos, handlers
│   ├── config.py               # Variables de entorno → Settings
│   ├── texts.py                # Textos del menú y la ayuda
│   ├── download_queue.py       # Cola de descargas de audio/video
│   ├── db.py                   # SQLite (caché de file_id, usuarios)
│   ├── handlers/
│   │   ├── books.py            # /libro, /fuente, /convertir y botones de libros
│   │   ├── menu.py             # /start y menú principal
│   │   ├── audio.py · video.py # /audio, /apple, /video
│   │   ├── admin.py            # /stats, /ban, /broadcast…
│   │   └── …
│   ├── services/
│   │   ├── sources.py          # Registro de fuentes de libros (orden = prioridad)
│   │   ├── http_utils.py       # fetch / fetch_book: reintentos, límites, errores
│   │   ├── open_library.py · internet_archive.py · dbooks.py
│   │   ├── libgen.py · gutenberg.py · standard_ebooks.py
│   │   ├── books_api.py        # API de libros propia (opcional)
│   │   └── ytdlp_download.py   # Audio/video
│   └── utils/
├── src/background_worker.py    # Worker: /data/incoming → /data/processed
├── tests/                      # pytest (conftest.py con fakes HTTP compartidos)
├── docs/libros.md              # Documentación técnica de libros
├── main.py · main_worker.py    # Entrypoints
├── Makefile                    # make test | test-live | lint | check | dev
├── Dockerfile · docker-compose.yml · fly.toml
└── .github/workflows/          # CI (cada push) y live-sources (semanal)
```

---

## ✅ Requisitos Previos

Antes de comenzar, asegúrate de tener instalado:

- Python 3.11 o superior
- Git
- FFmpeg (`sudo apt install ffmpeg` en Linux / `brew install ffmpeg` en macOS)
- Calibre (para conversión de libros): https://calibre-ebook.com/download
- Una cuenta de Telegram y un bot creado con [@BotFather](https://t.me/BotFather)

---

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/N0x370z/Chatbot.git
cd Chatbot
```

### 2. Crear un entorno virtual

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Abre el archivo `.env` y rellena los valores:

```env
TELEGRAM_BOT_TOKEN=tu_token_aqui
ADMIN_USER_ID=tu_id_de_telegram
MAX_FILE_SIZE_MB=50
DOWNLOAD_PATH=./downloads
INCOMING_FILES_PATH=/data/incoming
PROCESSED_FILES_PATH=/data/processed
WORKER_POLL_INTERVAL_SEC=1.0
```

---

## ⚙️ Configuración

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot (obtenido con BotFather) | — |
| `ADMIN_USER_ID` | ID de Telegram del administrador | — |
| `MAX_FILE_SIZE_MB` | Tamaño máximo de archivo en MB | `50` |
| `DOWNLOAD_PATH` | Ruta temporal de descargas | `./downloads` |
| `INCOMING_FILES_PATH` | Carpeta de archivos entrantes | `/data/incoming` |
| `PROCESSED_FILES_PATH` | Carpeta de archivos procesados | `/data/processed` |
| `CALIBRE_LIBRARY_PATH` | Ruta de biblioteca de Calibre (opcional) | vacío |
| `WORKER_POLL_INTERVAL_SEC` | Intervalo del loop principal del worker | `1.0` |
| `LOG_LEVEL` | Nivel de logging (`INFO`, `DEBUG`) | `INFO` |
| `ALLOWED_USER_IDS` | IDs autorizados, separados por coma (vacío = todos) | vacío |
| `MAX_UPLOAD_SIZE_MB` | Tamaño máximo de archivos que envían los usuarios (Telegram limita a los bots a 20 MB) | `50` |
| `RATE_LIMIT_WINDOW_SEC` / `RATE_LIMIT_MAX_REQUESTS` | Límite de peticiones por usuario | `60` / `10` |
| `SSL_VERIFY` | Verificar certificados HTTPS salientes | `true` |
| `BOOKS_API_BASE_URL` | API de libros propia; si se define, pasa a ser la fuente por defecto | vacío |
| `BOOKS_API_KEY` (+ `_HEADER`, `_PREFIX`) | Clave de esa API; solo se envía a ella | vacío |
| `BOOKS_API_SEARCH_PATH` / `BOOKS_API_DOWNLOAD_PATH` / `BOOKS_API_QUERY_PARAM` | Rutas y parámetro de la API | `books/search` / `books/{id}/download` / `q` |
| `BOOKS_API_MAX_RESULTS` | Resultados por página en `/libro` | `8` |
| `BOOKS_API_TIMEOUT_SEC` | Timeout de la API propia | `60` |

> ⚠️ Nunca subas tu archivo `.env` al repositorio. Está incluido en `.gitignore`.

---

## 🤖 Uso del Bot

Una vez configurado, ejecuta el bot con:

```bash
python main.py
```

En otra terminal, ejecuta el worker en segundo plano:

```bash
python main_worker.py
```

O con Docker:

```bash
docker build -t telegram-media-bot .
docker run --env-file .env telegram-media-bot
```

### ☁️ Despliegue en Fly.io (Recomendado)

El proyecto incluye un archivo `fly.toml` listo para ser usado. Fly.io permite ejecutar tanto el bot como el worker en la misma instancia usando procesos separados y volúmenes persistentes.

1. Instala [flyctl](https://fly.io/docs/hands-on/install-cli/) e inicia sesión.
2. Lanza la aplicación (sin desplegar inmediatamente):
   ```bash
   fly launch --no-deploy
   ```
3. Crea un volumen persistente para la base de datos SQLite (1GB es suficiente):
   ```bash
   fly volume create bot_data --region iad --size 1
   ```
4. Configura las variables secretas necesarias:
   ```bash
   fly secrets set TELEGRAM_BOT_TOKEN="tu_token" ADMIN_USER_ID="tu_id"
   ```
5. Despliega la aplicación:
   ```bash
   fly deploy
   ```

---

## 🐳 Docker Compose

Para levantar bot y worker juntos:

```bash
docker compose up --build
```

El archivo `docker-compose.yml` define dos servicios:

- `bot`: ejecuta `python main.py`
- `worker`: ejecuta `python main_worker.py`

Con volúmenes compartidos:

- `./downloads:/app/downloads`
- `/data/incoming:/data/incoming`
- `/data/processed:/data/processed`

Y toma variables desde `.env`.

> En macOS, si no puedes escribir en `/data`, usa rutas locales (`./data/incoming` y `./data/processed`) en tu `.env`.

---

## 📋 Comandos Disponibles

| Comando | Descripción |
|---|---|
| `/start` | Inicia el bot y muestra el menú principal |
| `/libro <título o autor>` | Busca libros; toca un resultado para descargarlo o «🔁 Otra fuente» |
| `/fuente [clave]` | Selector de fuente con botones (`open_library`, `internet_archive`, `dbooks`, `libgen`, `gutenberg`, `standard_ebooks`) |
| `/convertir <formato>` | Convierte el último PDF/EPUB que enviaste (epub, pdf, mobi, azw3, txt) |
| `/audio <nombre o URL>` | Descarga y envía audio (MP3/M4A) |
| `/formato_audio` | Elegir formato de audio (MP3/M4A/OPUS/FLAC) |
| `/video <nombre o URL>` | Descarga y envía video (MP4) |
| `/apple <nombre o URL>` | Descarga en formato compatible con iPod/Apple (M4A/AAC/M4B) |
| `/jobs` | Ver estado de descargas en cola |
| `/cancelar` | Cancelar la última descarga pendiente |
| `/estado` | Ver tus preferencias (fuente, formato de audio) |
| `/version` · `/ping` | Versión del bot · prueba de conexión |
| `/ayuda` | Muestra la lista de comandos |
| `/stats` | (Solo admin) Estadísticas de uso |
| `/diagnostico` | (Solo admin) Hace una búsqueda real en cada fuente de libros y muestra cuáles funcionan |
| `/ban` · `/unban` · `/broadcast` | (Solo admin) Gestión de usuarios y avisos |

---

## 📚 Libros: fuentes y descargas

Por defecto se busca en **Open Library**, que solo devuelve obras de dominio público con copia descargable, y se descarga su EPUB/PDF desde Internet Archive. Si una fuente no da resultados, el bot consulta el resto en paralelo y avisa de cuál usó.

| Fuente | Ideal para |
|---|---|
| Open Library / Internet Archive | Clásicos y libros de dominio público |
| dBooks | Programación y tecnología (PDF gratuitos) |
| Libgen | Libros técnicos y académicos |
| Gutenberg / Standard Ebooks | Clásicos (sus APIs fallan a menudo; van al final del respaldo) |

Las descargas se limitan a `MAX_FILE_SIZE_MB`, que por defecto es 50 MB, el máximo que Telegram permite enviar a un bot.

El funcionamiento interno está en **[docs/libros.md](docs/libros.md)**: cómo se piden los recursos, cómo añadir una fuente y problemas conocidos de cada API.

---

## 🧪 Pruebas

```bash
make test        # tests rápidos, sin red (~2 s)
make lint        # ruff
make check       # lint + test (hazlo antes de cada commit)
make test-live   # busca y descarga un libro real en cada fuente (minutos, requiere red)
```

- CI (`.github/workflows/ci.yml`) ejecuta `ruff` y `pytest` en cada push y PR a `main` y `BearDev`.
- `live-sources.yml` ejecuta `make test-live` cada lunes (y a mano desde *Actions*). Así se detecta cuándo una fuente externa cambia o cae, aunque el código no haya cambiado.
- Los tests `live` están marcados con `@pytest.mark.live` y quedan excluidos de `pytest` por defecto (`pyproject.toml`).

> En macOS, si ves `CERTIFICATE_VERIFY_FAILED`, ejecuta `Install Certificates.command` de tu instalación de Python o exporta `SSL_CERT_FILE=$(python -m certifi)`.

---

## 🤝 Contribuir al Repositorio

Esta sección explica paso a paso cómo añadir cambios al proyecto una vez que el repositorio ya ha sido creado.

### Flujo de trabajo recomendado

#### 1. Asegúrate de tener la versión más reciente

```bash
git pull origin main
```

#### 2. Crea una rama nueva para tu cambio

Nunca trabajes directamente en `main`. Crea una rama con un nombre descriptivo:

```bash
git checkout -b feature/nombre-de-la-funcionalidad
# Ejemplos:
# git checkout -b feature/soporte-epub
# git checkout -b fix/error-descarga-mp3
# git checkout -b docs/actualizar-readme
```

#### 3. Realiza tus cambios

Edita, crea o elimina los archivos que necesites. Una vez listos:

```bash
# Ver qué archivos cambiaron
git status

# Añadir archivos específicos al staging area
git add bot/handlers/audio.py

# O añadir todos los cambios de golpe
git add .
```

Antes de hacer commit, comprueba que todo pasa:

```bash
make check
```

#### 4. Haz un commit con un mensaje claro

```bash
git commit -m "feat: añadir soporte para formato M4B (audiolibros Apple)"
```

> 💡 **Convención de mensajes recomendada:**
> - `feat:` para nuevas funcionalidades
> - `fix:` para corrección de errores
> - `docs:` para cambios en documentación
> - `refactor:` para refactorizaciones sin cambio funcional
> - `test:` para añadir o modificar pruebas

#### 5. Sube tu rama al repositorio remoto

```bash
git push origin feature/nombre-de-la-funcionalidad
```

#### 6. Abre un Pull Request (PR)

Ve a GitHub y abre un Pull Request desde tu rama hacia `main`. Describe qué hiciste y por qué.

#### 7. Tras la revisión, fusiona y limpia

```bash
# Vuelve a main
git checkout main

# Trae los cambios fusionados
git pull origin main

# Elimina la rama local que ya no necesitas
git branch -d feature/nombre-de-la-funcionalidad
```

### Añadir nuevas dependencias

Si instalas una nueva librería, actualiza el archivo `requirements.txt`:

```bash
pip install nombre-libreria
pip freeze > requirements.txt
git add requirements.txt
git commit -m "chore: añadir dependencia nombre-libreria"
```

### Archivos que NUNCA deben subirse

El `.gitignore` ya está configurado para excluir:

```
.env
downloads/
__pycache__/
*.pyc
venv/
.DS_Store
```

Si accidentalmente añadiste algo que no debía subirse, puedes quitarlo del seguimiento:

```bash
git rm --cached archivo-sensible.env
git commit -m "fix: eliminar archivo sensible del repositorio"
```

---

## 🗺 Roadmap

- [x] Estructura base del proyecto
- [x] Handler de descarga de libros (PDF/EPUB)
- [x] Handler de audio MP3 y M4A
- [x] Handler de video MP4
- [x] Soporte para formatos Apple (M4A, AAC, M4B)
- [x] Sistema de colas para múltiples usuarios
- [x] Panel de administración con estadísticas
- [x] Dockerización del bot
- [x] Despliegue en servidor VPS / Railway / Fly.io
- [x] Descarga de libros desde Open Library / Internet Archive con respaldo entre fuentes
- [x] Pruebas automáticas contra las fuentes reales (semanales)

---

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.

---

> Desarrollado con ❤️ usando Python y la API de Telegram.
