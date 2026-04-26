"""Textos fijos del bot (menú, ayuda) — un solo sitio para editar copy."""

WELCOME_HTML = (
    "¡Hola! Soy <b>TelegramMediaBot</b>.\n\n"
    "Elige una opción del menú y te digo exactamente qué comando usar.\n\n"
    "<b>Tip rápido</b>: para descargar pega una URL con /audio o /video.\n\n"
    "<b>Para libros</b>: usa /fuente para elegir fuente si una falla."
)

HELP_HTML = (
    "<b>📚 Libros</b>\n"
    "• /libro &lt;título o autor&gt; — buscar y descargar libro\n"
    "• /fuente — elegir fuente (Open Library / Gutenberg / Libgen)\n"
    "• /convertir &lt;formato&gt; — convertir libro subido (epub/pdf/mobi)\n\n"
    "<b>🎵 Audio</b>\n"
    "• /audio &lt;url&gt; — descargar audio\n"
    "• /apple &lt;url&gt; — audio M4A (Apple/iPod)\n"
    "• /formato_audio — elegir formato (MP3 / M4A / OPUS / FLAC)\n\n"
    "<b>🎬 Video</b>\n"
    "• /video &lt;url&gt; — descargar video (MP4, mínimo 480p)\n\n"
    "<b>⚙️ General</b>\n"
    "• /ayuda — esta lista\n"
    "• /ping — prueba de conexión\n"
    "• /jobs — estado de descargas en cola\n"
    "• Enviar PDF/EPUB — guardar en biblioteca\n"
    "• /stats — estadísticas (solo admin)\n\n"
    "<b>Ejemplo</b>\n"
    "<code>/fuente libgen</code>\n"
    "<code>/libro hacking the art of exploitation</code>\n"
    "<code>/formato_audio opus</code>\n"
    "<code>/audio https://youtu.be/...</code>"
)

MENU_HINTS_HTML = {
    "books": (
        "<b>Buscar libro</b>\n"
        "Comando: <code>/libro &lt;título o autor&gt;</code>\n"
        "Usa <code>/fuente</code> para elegir entre Open Library, Gutenberg o Libgen.\n"
        "Ejemplo: <code>/libro harry potter</code>"
    ),
    "audio": (
        "<b>Descargar audio</b>\n"
        "Envía: <code>/audio &lt;url&gt;</code>\n"
        "Usa <code>/formato_audio</code> para elegir formato: MP3, M4A, OPUS o FLAC.\n"
        "Ejemplo: <code>/audio https://youtu.be/...</code>"
    ),
    "video": (
        "<b>Descargar video</b>\n"
        "Envía: <code>/video &lt;url&gt;</code>\n"
        "Ejemplo: <code>/video https://youtu.be/...</code>"
    ),
    "apple": (
        "<b>Apple (M4A)</b>\n"
        "Envía: <code>/apple &lt;url&gt;</code>\n"
        "Ideal para iPhone/iPod. Ejemplo: <code>/apple https://youtu.be/...</code>"
    ),
}
