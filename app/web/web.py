
"""
Web Layer - Flask Application.

Handles HTTP requests for Captive Portal.
Does not contain business logic - delegates to PortalEngine.
"""

from flask import Flask, request, redirect, render_template_string
from app import logger, get_settings, create_controller
from app.engine import PortalEngine


# Простой HTML шаблон для GET запроса
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Captive Portal</title>
</head>
<body>
    <h1>Добро пожаловать</h1>
    <form method="post">
        <button type="submit">Подключиться</button>
    </form>
</body>
</html>
"""

# HTML шаблон для успешной авторизации
SUCCESS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Успешно</title>
</head>
<body>
    <h1>Вы успешно подключены</h1>
</body>
</html>
"""

# HTML шаблон для ошибки
ERROR_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Ошибка</title>
</head>
<body>
    <h1>Ошибка подключения</h1>
    <p>{{ error_message }}</p>
</body>
</html>
"""


def create_app() -> Flask:
    """
    Create and configure Flask application.
    
    Returns:
        Flask: Configured Flask application instance.
    """
    app = Flask(__name__)
    
    # Создаем контроллер и движок один раз при инициализации приложения
    controller = create_controller()
    engine = PortalEngine(controller)
    
    @app.route("/", methods=["GET"])
    def index():
        """
        Handle GET request - show portal page with connect button.
        """
        logger.info("GET / - Showing portal page")
        return render_template_string(INDEX_HTML)
    
    @app.route("/", methods=["POST"])
    def authorize():
        """
        Handle POST request - authorize client.
        
        Parameters from Omada (in query string):
        - clientMac: MAC address of the client
        - site: Site ID
        - redirectUrl: URL to redirect after successful authorization
        """
        # Получаем параметры из query string
        client_mac = request.args.get("clientMac")
        site_id = request.args.get("site")
        redirect_url = request.args.get("redirectUrl")
        
        logger.info(f"POST / - Authorization request: site={site_id}, mac={client_mac}")
        
        # Вызываем движок для авторизации
        result = engine.authorize_client(site_id, client_mac)
        
        if result.success:
            logger.info(f"Authorization successful for {client_mac}")
            
            # Если есть redirectUrl - делаем редирект
            if redirect_url:
                logger.info(f"Redirecting to {redirect_url}")
                return redirect(redirect_url)
            else:
                # Если redirectUrl нет - показываем страницу успеха
                logger.info("No redirectUrl provided, showing success page")
                return render_template_string(SUCCESS_HTML)
        else:
            # Авторизация не удалась - показываем ошибку
            logger.error(f"Authorization failed: {result.message}")
            return render_template_string(ERROR_HTML, error_message=result.message), 400
    
    return app
