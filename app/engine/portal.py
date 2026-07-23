"""Portal Engine - центральное ядро бизнес-логики платформы."""

import logging

from app.models import Result
from app.exceptions import PortalError


def get_logger() -> logging.Logger:
    """Get the global logger instance."""
    from app.logger import logger
    return logger


class PortalEngine:
    """
    Portal Engine отвечает исключительно за бизнес-логику.
    
    Он не знает о HTTP, Flask, HTML или конкретной реализации контроллера.
    Работает только через интерфейс Controller Provider и возвращает Result.
    """

    def __init__(self, controller):
        """
        Инициализация движка.
        
        Args:
            controller: Экземпляр контроллера, реализующий интерфейс Provider.
                       Внедряется извне (Dependency Injection).
        """
        if controller is None:
            raise PortalError("Controller provider cannot be None")
        
        self._controller = controller
        self._logger = get_logger()

    def authorize_client(self, site_id: str, client_mac: str) -> Result:
        """
        Авторизация клиента в сети.
        
        Args:
            site_id: Идентификатор сайта.
            client_mac: MAC-адрес клиента.
            
        Returns:
            Result: Объект результата операции.
        """
        # Валидация параметров
        if not site_id or not isinstance(site_id, str) or not site_id.strip():
            return Result.fail(
                error="INVALID_SITE_ID",
                message="Site ID is required and cannot be empty"
            )
        
        if not client_mac or not isinstance(client_mac, str) or not client_mac.strip():
            return Result.fail(
                error="INVALID_CLIENT_MAC",
                message="Client MAC address is required and cannot be empty"
            )
        
        # Делегирование вызова контроллеру
        # Engine не анализирует внутреннюю логику ответа, только возвращает Result
        # Если контроллер вернул ошибку (например, CONTROLLER_OFFLINE), 
        # она сохраняется без изменений.
        try:
            result = self._controller.authorize(site_id, client_mac)
            return result
        except Exception as e:
            # Логирование критической ошибки выполнения (не бизнес-логики)
            self._logger.error(f"Authorization failed due to unexpected error: {str(e)}")
            return Result.fail(
                error="ENGINE_INTERNAL_ERROR",
                message=f"Unexpected error during authorization: {str(e)}"
            )
