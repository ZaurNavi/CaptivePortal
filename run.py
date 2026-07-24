#!/usr/bin/env python3
"""
Captive Portal - Main Entry Point.

This is the only file that should be executed directly.
No other module should be run standalone.
"""

import signal
import sys
import atexit

from app import logger, get_settings
from app.web.web import create_app, auth_executor


def shutdown_handler():
    """
    Gracefully shut down background workers.
    wait=True: позволяет текущим задачам авторизации завершиться.
    cancel_futures=False: не отменяет задачи, которые уже начали выполняться.
    """
    logger.info("Shutting down authentication worker executor...")
    auth_executor.shutdown(wait=True, cancel_futures=False)
    logger.info("Authentication worker executor stopped successfully.")


def signal_handler(signum, frame):
    """
    Обработчик сигналов операционной системы (SIGINT / SIGTERM).
    Гарантирует вызов shutdown_handler при завершении процесса.
    """
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_handler()
    sys.exit(0)


def main():
    """Main application entry point."""
    logger.info("Starting Captive Portal")

    # 1. Регистрируем обработчики корректного завершения
    atexit.register(shutdown_handler)
    signal.signal(signal.SIGINT, signal_handler)   # Перехват Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Перехват kill / systemctl stop

    # 2. Load configuration
    settings = get_settings()
    logger.info("Configuration loaded")

    # 3. Create Flask application
    app = create_app()
    logger.info("Web application created")

    # 4. Run Flask server
    logger.info(f"Starting server on {settings['host']}:{settings['port']}")
    
    try:
        app.run(
            host=settings["host"],
            port=settings["port"],
            debug=settings["debug"]
        )
    except KeyboardInterrupt:
        # Дополнительная страховка для режима отладки Flask
        logger.info("KeyboardInterrupt caught in main loop.")
    finally:
        # Гарантированный вызов очистки при любом выходе из app.run()
        shutdown_handler()


if __name__ == "__main__":
    main()
