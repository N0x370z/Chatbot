# 📚 Libros: fuentes, peticiones y pruebas

Documentación técnica de la búsqueda y descarga de libros (`/libro`, `/fuente`).

## Flujo para el usuario

1. `/libro <título o autor>`: el bot responde «🔎 Buscando…» y edita ese mensaje con los resultados (botones, 8 por página).
2. Si la fuente elegida no da resultados, se consultan **todas las demás en paralelo** y se muestran los de la primera, según la prioridad del registro. El mensaje indica qué fuente se usó.
3. Tocar un resultado lo descarga. El progreso se muestra en un mensaje aparte y **la lista se conserva**, así que si una descarga falla se puede elegir otro resultado.
4. **🔁 Otra fuente** (debajo de los resultados) repite la misma búsqueda en la fuente que elijas.
5. `/fuente` abre un selector con botones para la fuente por defecto. También funciona `/fuente <clave>` y el botón «⚙️ Elegir fuente» del menú.

Los archivos ya enviados se reenvían al instante desde la caché de `file_id` de Telegram (SQLite).

## Fuentes

El orden es la prioridad de respaldo (`bot/services/sources.py`):

| Clave | Fuente | Qué ofrece | Cómo descarga |
|---|---|---|---|
| `open_library` *(por defecto)* | [Open Library](https://openlibrary.org) | Clásicos de dominio público | Busca solo obras con `ebook_access:public`. Al descargar, toma la lista `ia` de la obra, filtra en Internet Archive las copias libres y descarga la primera que funcione. |
| `internet_archive` | [Internet Archive](https://archive.org) | Millones de textos digitalizados | Busca ítems no restringidos que tengan EPUB/PDF. Prefiere EPUB y, dentro de cada formato, el archivo más pequeño. Prueba hasta 3 archivos. |
| `dbooks` | [dBooks](https://www.dbooks.org) | Libros técnicos gratuitos (PDF) | API JSON con enlace directo. |
| `libgen` | [libgen.li](https://libgen.li) | Catálogo técnico/académico amplio | Extrae datos del HTML, sigue `ads.php` → `get.php` (solo dominios permitidos). |
| `gutenberg` | [Gutendex](https://gutendex.com) | Project Gutenberg | Cae con frecuencia; timeout corto. |
| `standard_ebooks` | [Standard Ebooks](https://standardebooks.org) | EPUB cuidados | El feed OPDS exige cuenta Patrons Circle (HTTP 401). |

Si `BOOKS_API_BASE_URL` está configurada, la fuente por defecto pasa a ser esa API propia (ver `bot/services/books_api.py`).

### Particularidades conocidas

- **Internet Archive** reporta los formatos con mayúsculas (`"EPUB"`, `"Text PDF"`). Se comparan en minúsculas. Los archivos con `private: "true"` son de préstamo y se descartan.
- **Internet Archive es lento** en descargas grandes: pueden tardar un par de minutos. Cada descarga completa tiene un límite de 5 minutos (`DOWNLOAD_DEADLINE_SEC`).
- **Libgen** sirve una página vacía de nginx a User-Agents que no son de navegador, así que sus peticiones usan uno de Firefox. Los parámetros de búsqueda actuales son `columns[]`, `objects[]` y `topics[]`.
- Solo se aceptan PDF, EPUB y MOBI. Se validan por *magic bytes*, no por la extensión ni el `Content-Type`.

## Cómo se piden los recursos

Todas las fuentes usan `bot/services/http_utils.py`:

- **`fetch(session, url, source=..., parse="json"|"text"|"bytes", params=..., headers=...)`**: búsquedas y metadatos. Reintenta ante timeouts, errores de red y HTTP 5xx (esperas en `RETRY_DELAYS`), pero no ante 4xx. Todo fallo se convierte en `BooksApiError` con un mensaje para el usuario que nombra la fuente. Los parámetros con listas (`fl[]`) se expanden a pares repetidos.
- **`fetch_book(session, url, source=..., limit=...)`**: descarga en *streaming* y corta en cuanto se supera `MAX_FILE_SIZE_MB`, sin cargar el archivo completo si es demasiado grande. Valida el tipo y devuelve `Downloaded(data, kind, content_type, filename)`, con el nombre del `Content-Disposition` ya saneado.

La sesión HTTP es compartida (`bot_data["http_session"]`) y solo lleva el User-Agent del bot. La clave `BOOKS_API_KEY` se añade **solo** a las peticiones de la API propia (`books_api.auth_headers`), nunca a las fuentes públicas.

## Añadir una fuente

1. Crea `bot/services/<fuente>.py` con:
   - una función pura `parse_search(payload, max_results) -> list[BookResult]`,
   - `async def search_x(session, query, max_results)` que llama a `fetch` y a `parse_search`,
   - `async def download_x(session, book_id, settings) -> tuple[bytes, str]` que usa `fetch_book`.
2. Regístrala en `_ALL` de `bot/services/sources.py` (clave, nombre, descripción, funciones). La posición define su prioridad de respaldo. El selector de `/fuente`, el respaldo y la descarga salen del registro, así que no hay que tocar el handler.
3. Añade tests:
   - el parser en `tests/test_book_sources.py::test_parse_search` (una fila del `parametrize`),
   - la descarga en `test_source_download_happy_path`,
   - un caso en `tests/test_live_sources.py`.

## Pruebas

| Comando | Qué hace | Cuándo corre |
|---|---|---|
| `make test` | Tests rápidos sin red (~2 s) | CI en cada push/PR |
| `make lint` | `ruff check .` | CI en cada push/PR |
| `make check` | lint + test | antes de hacer commit |
| `make test-live` | Busca y descarga un libro real en cada fuente | CI semanal (`live-sources.yml`) y manual |

- `tests/conftest.py` define `FakeSession` y `FakeResponse`, que responden por fragmento de URL y registran las peticiones en `session.calls`. También define el fixture `settings` y desactiva las esperas entre reintentos.
- Los errores de red/HTTP se prueban **una sola vez**, en `tests/test_http_utils.py`. Los tests de cada fuente solo cubren lo específico: interpretación de la respuesta y selección de archivo.
- Los tests `live` de Gutenberg y Standard Ebooks están marcados `xfail`, porque esas APIs fallan por motivos externos. Si vuelven a funcionar, aparecen como `XPASS`.
- Si el workflow semanal falla, revisa el log: indica qué fuente dejó de buscar o descargar.

### Problemas frecuentes

- **`CERTIFICATE_VERIFY_FAILED` en macOS**: el Python de python.org no trae certificados. Ejecuta `/Applications/Python\ 3.x/Install\ Certificates.command`, o exporta `SSL_CERT_FILE=$(python -m certifi)`. Los tests live ya usan `certifi` si está instalado.
- **Una fuente devuelve 0 resultados**: ejecuta `pytest -m live -k <clave> -v` para ver el error real.
