"""Textos fijos del bot (menú, ayuda) — un solo sitio para editar copy."""

WELCOME_HTML = (
    "¡Hola! Soy <b>TelegramMediaBot</b>.\n\n"
    "Elige una opción del menú y te digo exactamente qué comando usar.\n\n"
    "<b>Tip rápido</b>: para descargar pega una URL con /audio o /video."
)

HELP_HTML = (
    "<b>Comandos</b>\n"
    "• /libro &lt;título o autor&gt; — libros vía API (configura BOOKS_API_BASE_URL)\n"
    "• /audio &lt;url&gt; — audio\n"
    "• /video &lt;url&gt; — video (MP4 cuando es posible)\n"
    "• /apple &lt;url&gt; — audio M4A (Apple)\n"
    "• /ayuda — esta lista\n"
    "• /ping — prueba rápida de vida\n"
    "• /jobs — ver estado de descargas en cola\n"
    "• Enviar PDF/EPUB — guarda el archivo en almacenamiento local\n"
    "• /stats — uso (solo administrador)\n\n"
    "<b>Ejemplo</b>\n"
    "<code>/audio https://www.youtube.com/watch?v=…</code>"
)

MENU_HINTS_HTML = {
    "books": (
        "<b>Buscar libro</b>\n"
        "Comando: <code>/libro &lt;título o autor&gt;</code>\n"
        "Requiere <code>BOOKS_API_BASE_URL</code> en <code>.env</code>.\n"
        "Ejemplo: <code>/libro harry potter</code>"
    ),
    "audio": (
        "<b>Descargar audio</b>\n"
        "Envía: <code>/audio &lt;url&gt;</code>\n"
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
