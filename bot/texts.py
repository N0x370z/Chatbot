"""Textos fijos del bot (menú, ayuda) — un solo sitio para editar copy."""

WELCOME_HTML = (
    "👋 ¡Hola! Soy tu asistente de descargas.\n\n"
    "📚 <b>Libros</b> · 🎵 <b>Audio</b> · 🎬 <b>Video</b>\n\n"
    "Elige una opción del menú, envía una URL directamente "
    "o escribe <code>/ayuda</code> para ver todos los comandos."
)

HELP_HTML = (
    "<b>📚 Libros</b>\n"
    "• /libro &lt;título o autor&gt; — buscar y descargar\n"
    "• /fuente — elegir fuente de libros:\n"
    "  <code>standard_ebooks</code> · <code>gutenberg</code> · <code>libgen</code>\n"
    "  <code>open_library</code> · <code>internet_archive</code> · <code>dbooks</code>\n"
    "• /convertir &lt;formato&gt; — convertir archivo subido (epub/pdf/mobi/azw3/txt)\n\n"
    "<b>🎵 Audio</b>\n"
    "• /audio &lt;url&gt; — descargar audio (YouTube, SoundCloud, Bandcamp…)\n"
    "• /apple &lt;url&gt; — audio en M4A vía FFmpeg\n"
    "• /formato_audio — elegir formato: MP3 · M4A · OPUS · FLAC\n\n"
    "<b>🎬 Video</b>\n"
    "• /video &lt;url&gt; — descargar video en MP4\n\n"
    "<b>⚙️ General</b>\n"
    "• /jobs — estado de descargas en cola\n"
    "• /cancelar — cancelar la última descarga pendiente\n"
    "• /estado — ver tus preferencias actuales\n"
    "• /version — versión del bot\n"
    "• /ping — prueba de conexión\n"
    "• Enviar PDF/EPUB — guardar en biblioteca\n\n"
    "<b>Ejemplos</b>\n"
    "<code>/fuente libgen</code>\n"
    "<code>/libro hacking the art of exploitation</code>\n"
    "<code>/formato_audio opus</code>\n"
    "<code>/audio https://youtu.be/...</code>"
)

MENU_HINTS_HTML = {
    "books": (
        "<b>📚 Buscar libro</b>\n\n"
        "Comando: <code>/libro &lt;título o autor&gt;</code>\n\n"
        "Fuentes disponibles (usa /fuente para cambiar):\n"
        "• <code>standard_ebooks</code> — ediciones cuidadas de clásicos\n"
        "• <code>gutenberg</code> — mayor catálogo de dominio público\n"
        "• <code>libgen</code> — amplia biblioteca técnica y general\n"
        "• <code>internet_archive</code> — archivos digitalizados\n"
        "• <code>dbooks</code> — libros técnicos gratuitos\n"
        "• <code>open_library</code> — catálogo (sin descarga directa)\n\n"
        "Ejemplo: <code>/libro clean code robert martin</code>"
    ),
    "audio": (
        "<b>🎵 Descargar audio</b>\n\n"
        "Comando: <code>/audio &lt;url&gt;</code>\n\n"
        "Fuentes: YouTube, SoundCloud, Bandcamp y más.\n"
        "Apple Music y Spotify <b>no son compatibles</b> (DRM).\n\n"
        "Cambia el formato con /formato_audio (MP3/M4A/OPUS/FLAC).\n\n"
        "Ejemplo: <code>/audio https://youtu.be/dQw4w9WgXcQ</code>"
    ),
    "video": (
        "<b>🎬 Descargar video</b>\n\n"
        "Comando: <code>/video &lt;url&gt;</code>\n\n"
        "Descarga en MP4. Se elige la mejor calidad disponible.\n\n"
        "Ejemplo: <code>/video https://youtu.be/dQw4w9WgXcQ</code>"
    ),
}
