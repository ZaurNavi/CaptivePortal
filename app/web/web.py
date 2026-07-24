"""
Web Layer - Flask Application.

Handles HTTP requests for Captive Portal.
Delegates authorization to background AuthWorker to ensure non-blocking operation.
"""

import os
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, request, redirect, render_template

from app import logger, get_settings, create_controller
from app.engine import PortalEngine

# Импорты нового модуля аутентификации
from app.auth.manager import AuthSessionManager
from app.auth.worker import AuthWorker, log_auth_event
from app.auth.session import AuthStatus


# Глобальная инициализация менеджера и пула потоков (строго один экземпляр на процесс!)
# Это гарантирует, что при запуске с 1 worker и 4 threads (Gunicorn) 
# все запросы будут использовать общий словарь сессий.
auth_manager = AuthSessionManager()
auth_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="auth_worker_")


def create_app() -> Flask:
    """
    Create and configure Flask application.
    """
    # Указываем Flask путь к папке templates внутри app/web/
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
    app = Flask(__name__, template_folder=template_dir)
    
    # Создаем контроллер и движок один раз при инициализации приложения
    controller = create_controller()
    engine = PortalEngine(controller)
    
    # Создаем экземпляр Worker, передавая ему существующий controller (который реализует Provider)
    auth_worker = AuthWorker(provider=controller, session_manager=auth_manager)
    
    @app.route("/", methods=["GET"])
    def index():
        """
        Handle GET request - show portal page.
        """
        logger.info("GET / - Showing portal page")
        return render_template("portal.html")
    
    @app.route("/", methods=["POST"])
    def authorize():
        """
        Handle POST request - initiate asynchronous authorization process.
        """
        client_mac = request.args.get("clientMac")
        site_id = request.args.get("site")
        redirect_url = request.args.get("redirectUrl")
        client_ip = request.remote_addr
        
        logger.info(f"POST / - Authorization request: site={site_id}, mac={client_mac}, ip={client_ip}")
        
        try:
            # 1. Создаем или получаем существующую сессию
            session, is_new = auth_manager.create_or_get(site_id, client_mac, client_ip)
            
            if not is_new:
                # Сессия уже существует. Проверяем её состояние через публичный snapshot
                snapshot = auth_manager.snapshot(session)
                
                if snapshot["is_active"] or not snapshot["worker_finished"]:
                    # Worker всё ещё работает
                    log_auth_event("SESSION_ALREADY_ACTIVE", session, level=logging.WARNING)
                    return render_template(
                        "portal.html", 
                        error_message="Процесс подключения уже запущен, пожалуйста, подождите.", 
                        retry=True
                    ), 400
                else:
                    # Сессия завершена (например, AUTHORIZED в периоде retention)
                    log_auth_event("SESSION_FINISHED", session, level=logging.INFO)
                    if snapshot["status"] == "AUTHORIZED":
                        if redirect_url:
                            return redirect(redirect_url)
                        return render_template("success.html")
                    else:
                        # Была ошибка или сброс, позволяем пользователю попробовать снова
                        return render_template(
                            "portal.html", 
                            error_message=f"Предыдущая попытка не удалась: {snapshot['last_error']}", 
                            retry=True
                        ), 400
            
            # 2. Это новая сессия. Запускаем фоновую задачу
            try:
                auth_executor.submit(auth_worker.process, session.session_id)
            except Exception as exc:
                # Если не удалось поставить задачу в очередь (например, приложение shuts down)
                auth_manager.update_status(session, AuthStatus.FAILED, error=f"Worker submission failed: {exc}")
                auth_manager.mark_worker_finished(session)
                log_auth_event("WORKER_SUBMISSION_FAILED", session, message=str(exc), level=logging.ERROR)
                return render_template(
                    "portal.html", 
                    error_message="Системная ошибка: не удалось запустить процесс подключения", 
                    retry=True
                ), 500
            
            # 3. Быстро возвращаем ответ, не дожидаясь завершения HTTP-запросов к Omada
            logger.info(f"Auth process started for {client_mac}, session: {session.session_id}")
            
            # Если есть URL для редиректа, возвращаем его. 
            # Браузер пользователя попытается перейти туда, а фоновый процесс в это время 
            # завершит авторизацию на контроллере.
            if redirect_url:
                return redirect(redirect_url)
            
            # Если редиректа нет, показываем страницу успеха (или можно сделать специальную "Connecting...")
            return render_template("success.html")
            
        except ValueError as e:
            logger.error(f"Invalid MAC address or parameters: {client_mac}")
            return render_template(
                "portal.html", 
                error_message="Неверные данные клиента", 
                retry=True
            ), 400
        except Exception as e:
            logger.error(f"Unexpected error in authorize route: {str(e)}")
            return render_template(
                "portal.html", 
                error_message="Внутренняя ошибка сервера", 
                retry=True
            ), 500
    
    return app
