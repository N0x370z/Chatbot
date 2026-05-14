"""Tests de configuración del logger."""

import logging
from logging.handlers import RotatingFileHandler
from unittest.mock import patch

from bot.utils.logger import setup_logging

def test_setup_logging_creates_rotating_file_handler():
    # Reiniciar handlers para evitar interferencias
    logger = logging.getLogger()
    old_handlers = list(logger.handlers)
    logger.handlers.clear()
    
    try:
        # Evitar crear el directorio 'logs' durante el test
        with patch("bot.utils.logger.Path.mkdir"):
            setup_logging("DEBUG")
        
        handlers = logging.getLogger().handlers
        
        rotating_handler = next((h for h in handlers if isinstance(h, RotatingFileHandler)), None)
        assert rotating_handler is not None, "Debe existir un RotatingFileHandler"
        
        assert rotating_handler.maxBytes == 10 * 1024 * 1024
        assert rotating_handler.backupCount == 5
        
    finally:
        # Restaurar handlers originales
        logger.handlers = old_handlers
