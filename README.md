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

- Búsqueda de libros por título, autor o ISBN
- Descarga y envío de archivos multimedia (MP3, MP4, M4A, AAC, MOV)
- Conversión de formatos de audio para compatibilidad con dispositivos Apple
- Sistema de búsqueda con resultados paginados
- Soporte para múltiples usuarios simultáneos
- Límite configurable de tamaño de archivo
- Registro de actividad (logs) por usuario
- Modo administrador con estadísticas de uso

---

## 🛠 Tecnologías

| Herramienta | Uso |
|---|---|
| Python 3.11+ | Lenguaje principal |
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
TelegramMediaBot/
├── bot/
│   ├── __init__.py
│   ├── main.py               # Punto de entrada del bot
│   ├── handlers/
│   │   ├── books.py          # Lógica para libros
│   │   ├── audio.py          # Lógica para MP3/M4A/AAC
│   │   ├── video.py          # Lógica para MP4/MOV
│   │   └── admin.py          # Comandos de administrador
│   ├── utils/
│   │   ├── downloader.py     # Descarga de archivos
│   │   ├── converter.py      # Conversión de formatos
│   │   └── logger.py         # Sistema de logs
│   └── config.py             # Configuración global
├── downloads/                # Carpeta temporal de descargas (en .gitignore)
├── tests/
│   └── test_handlers.py
├── .env.example              # Plantilla de variables de entorno
├── main.py                   # Entrypoint del bot
├── main_worker.py            # Entrypoint del worker
├── src/
│   └── background_worker.py  # Worker para /data/incoming -> /data/processed
├── config/
│   └── worker.env.example    # Variables de entorno del worker
├── .gitignore
├── requirements.txt
├── docker-compose.yml        # Orquestación bot + worker
├── Dockerfile                # (opcional) Para despliegue en contenedor
└── README.md
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
git clone https://github.com/tu-usuario/TelegramMediaBot.git
cd TelegramMediaBot
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
| `/libro <título o autor>` | Busca y envía un libro |
| `/fuente` | Elegir fuente de libros (Gutenberg/Libgen/Open Library) |
| `/convertir <formato>` | Convertir libro a otro formato |
| `/audio <nombre o URL>` | Descarga y envía audio (MP3/M4A) |
| `/formato_audio` | Elegir formato de audio (MP3/M4A/OPUS/FLAC) |
| `/video <nombre o URL>` | Descarga y envía video (MP4) |
| `/apple <nombre o URL>` | Descarga en formato compatible con iPod/Apple (M4A/AAC/M4B) |
| `/jobs` | Ver estado de descargas en cola |
| `/ping` | Prueba de conexión |
| `/ayuda` | Muestra la lista de comandos |
| `/stats` | (Solo admin) Estadísticas de uso |

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
- [ ] Despliegue en servidor VPS / Railway / Fly.io

---

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.

---

> Desarrollado con ❤️ usando Python y la API de Telegram.
