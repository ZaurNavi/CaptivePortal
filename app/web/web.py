"""
Web Layer - Flask Application.

Handles HTTP requests for Captive Portal.
Does not contain business logic - delegates to PortalEngine.
"""

import os
from flask import Flask, request, redirect, render_template
from app import logger, get_settings, create_controller
from app.engine import PortalEngine


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
        Handle POST request - authorize client.
        """
        client_mac = request.args.get("clientMac")
        site_id = request.args.get("site")
        redirect_url = request.args.get("redirectUrl")
        
        logger.info(f"POST / - Authorization request: site={site_id}, mac={client_mac}")
        
        result = engine.authorize_client(site_id, client_mac)
        
        if result.success:
            logger.info(f"Authorization successful for {client_mac}")
            if redirect_url:
                logger.info(f"Redirecting to {redirect_url}")
                return redirect(redirect_url)
            else:
                logger.info("No redirectUrl provided, showing success page")
                return render_template("success.html")
        else:
            else:
            logger.error(f"Authorization failed: {result.message}")
            # Передаем retry=True, чтобы шаблон знал — это повторная попытка
            return render_template(
                "portal.html",
                error_message=result.message,
                retry=True
            ), 400
    
    return app
