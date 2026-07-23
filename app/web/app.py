"""Flask web application for Captive Portal."""

from flask import Flask, request, render_template_string
from app import logger
from app.engine import PortalEngine
from app.controllers import create_controller


HTML_INDEX = """
<!DOCTYPE html>
<html>
<head>
    <title>Captive Portal</title>
</head>
<body>
    <h1>Добро пожаловать</h1>
    <p>Нажмите кнопку для подключения</p>
    <form method="POST">
        <button type="submit">Подключиться</button>
    </form>
</body>
</html>
"""

HTML_SUCCESS = """
<!DOCTYPE html>
<html>
<head>
    <title>Успех</title>
</head>
<body>
    <h1>Вы успешно подключены</h1>
</body>
</html>
"""

HTML_ERROR = """
<!DOCTYPE html>
<html>
<head>
    <title>Ошибка</title>
</head>
<body>
    <h1>Не удалось выполнить авторизацию</h1>
</body>
</html>
"""


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Initialize controller and engine
    controller = create_controller()
    engine = PortalEngine(controller)
    
    @app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "GET":
            logger.info("GET /")
            return render_template_string(HTML_INDEX)
        
        # POST request
        logger.info("POST /")
        
        # Get parameters from Omada
        client_mac = request.args.get("clientMac", "")
        site_id = request.args.get("site", "")
        redirect_url = request.args.get("redirectUrl", "")
        
        logger.info(f"Получен clientMac: {client_mac}")
        logger.info(f"Получен siteId: {site_id}")
        
        # Call Engine for authorization
        logger.info("Начата авторизация")
        result = engine.authorize_client(site_id, client_mac)
        
        if result.success:
            logger.info("Авторизация успешна")
            return render_template_string(HTML_SUCCESS)
        else:
            logger.info("Ошибка авторизации")
            return render_template_string(HTML_ERROR)
    
    return app
