"""Textos fijos del bot (menú, ayuda) — un solo sitio para editar copy."""

WELCOME_HTML = (
    "¡Hola! Soy <b>TelegramMediaBot</b>.\n\n"
    "Elige una opción del menú o usa los comandos con una <b>URL</b>.\n"
    "Las descargas usan <i>yt-dlp</i> y <i>FFmpeg</i> (deben estar instalados en el servidor)."
)

HELP_HTML = (
    "<b>Comandos</b>\n"
    "• /libro &lt;título o autor&gt; — libros (tu backend)\n"
    "• /audio &lt;url&gt; — audio\n"
    "• /video &lt;url&gt; — video (MP4 cuando es posible)\n"
    "• /apple &lt;url&gt; — audio M4A (Apple)\n"
    "• /ayuda — esta lista\n"
    "• /stats — uso (solo administrador)\n\n"
    "<b>Ejemplo</b>\n"
    "<code>/audio https://www.youtube.com/watch?v=…</code>"
)

MENU_HINTS_HTML = {
    "books": (
        "<b>Libros</b>\n"
        "Comando: <code>/libro &lt;título o autor&gt;</code>\n"
        "Aquí conectarás tu lógica de búsqueda y envío de archivos."
    ),
    "audio": (
        "<b>Audio</b>\n"
        "Envía: <code>/audio &lt;url&gt;</code>\n"
        "Se usa la mejor pista de audio disponible."
    ),
    "video": (
        "<b>Video</b>\n"
        "Envía: <code>/video &lt;url&gt;</code>\n"
        "Se intenta obtener MP4 vía yt-dlp + FFmpeg."
    ),
    "apple": (
        "<b>Apple (M4A)</b>\n"
        "Envía: <code>/apple &lt;url&gt;</code>\n"
        "Convierte a M4A cuando FFmpeg está instalado."
    ),
}
