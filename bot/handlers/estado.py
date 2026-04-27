from __future__ import annotations
import html
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, Application

async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return
    
    book_source = context.user_data.get("book_source", "open_library")
    audio_format = context.user_data.get("audio_format", "mp3")
    last_uploaded = context.user_data.get("last_uploaded_file", "ninguno")
    
    if last_uploaded != "ninguno":
        # extract just the filename if it's a path
        last_uploaded = str(last_uploaded).split("/")[-1]
        
    text = (
        "<b>Estado de Preferencias</b>\n\n"
        f"📚 <b>Fuente de libros:</b> <code>{html.escape(book_source)}</code>\n"
        f"🎵 <b>Formato de audio:</b> <code>{html.escape(audio_format)}</code>\n"
        f"📄 <b>Último archivo:</b> <code>{html.escape(last_uploaded)}</code>"
    )
    
    await msg.reply_html(text)

def register(application: Application) -> None:
    application.add_handler(CommandHandler("estado", cmd_estado))
