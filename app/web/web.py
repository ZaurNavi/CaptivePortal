"""
Web Layer - Flask Application.
"""

import os
from flask import Flask, request, redirect, render_template, jsonify
from concurrent.futures import ThreadPoolExecutor

from app import logger, get_settings, create_controller
from app.engine import PortalEngine
from app.auth.manager import AuthSessionManager
from app.auth.worker import AuthWorker, log_auth_event
from app.auth.session import AuthStatus

# Глобальная инициализация менеджера и пула потоков (строго один экземпляр на процесс)
auth_manager = AuthSessionManager()
# ThreadPoolExecutor создается один раз. max_workers=4 согласно ТЗ.
auth_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="auth_worker_")


def create_app() -> Flask:
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
    app = Flask(__name__, template_folder=template_dir)
    
    controller = create_controller()
    engine = PortalEngine(controller)
    
    # Передаем controller (который реализует ControllerInterface) в Worker
    auth_worker = AuthWorker(provider=controller, session_manager=auth_manager)
    
    @app.route("/", methods=["GET"])
    def index():
        logger.info("GET / - Showing portal page")
        return render_template("portal.html")
    
    @app.route("/", methods=["POST"])
    def authorize():
        client_mac = request.args.get("clientMac")
        site_id = request.args.get("site")
        redirect_url = request.args.get("redirectUrl")
        client_ip = request.remote_addr
        
        logger.info(f"POST / - Authorization request: site={site_id}, mac={client_mac}")
        
        try:
            # 1. Создаем или получаем сессию
            session, is_new = auth_manager.create_or_get(site_id, client_mac, client_ip)
            
            if not is_new:
                snapshot = auth_manager.snapshot(session)
                if snapshot["is_active"] or not snapshot["worker_finished"]:
                    log_auth_event("SESSION_ALREADY_ACTIVE", session, level=logging.WARNING)
                    return render_template("portal.html", error_message="Authorization is already in progress", retry=True), 400
                else:
                    # Сессия завершена (например, AUTHORIZED в retention)
                    log_auth_event("SESSION_FINISHED", session, level=logging.INFO)
                    if snapshot["status"] == "AUTHORIZED":
                        if redirect_url:
                            return redirect(redirect_url)
                        return render_template("success.html")
                    else:
                        return render_template("portal.html", error_message=f"Previous attempt failed: {snapshot['last_error']}", retry=True), 400
            
            # 2. Запускаем фоновую задачу
            try:
                auth_executor.submit(auth_worker.process, session.session_id)
            except Exception as exc:
                auth_manager.update_status(session, AuthStatus.FAILED, error=f"Worker submission failed: {exc}")
                auth_manager.mark_worker_finished(session)
                log_auth_event("WORKER_SUBMISSION_FAILED", session, message=str(exc), level=logging.ERROR)
                return render_template("portal.html", error_message="System error: unable to start process", retry=True), 500
            
            # 3. Быстро возвращаем управление, страница может показать "Подключение..."
            # В реальном сценарии фронтенд может опрашивать статус по session_id, 
            # но пока возвращаем стандартный успех, так как процесс пошел.
            logger.info(f"Auth process started for {client_mac}, session: {session.session_id}")
            
            # Если есть redirect_url, мы не можем его вернуть сразу, так как авторизация еще идет.
            # Но мы можем показать страницу "Ожидание подключения..." или сразу редирект, 
            # если контроллер применяет правила асинхронно. Оставляем редирект для совместимости.
            if redirect_url:
                return redirect(redirect_url)
            
            return render_template("success.html") # Или специальная страница "Connecting..."
            
        except ValueError as e:
            logger.error(f"Invalid MAC address: {client_mac}")
            return render_template("portal.html", error_message="Invalid client data", retry=True), 400
        except Exception as e:
            logger.error(f"Unexpected error in authorize route: {str(e)}")
            return render_template("portal.html", error_message="Internal server error", retry=True), 500
    
    return app
