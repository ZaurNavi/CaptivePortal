"""
Result Model for Captive Portal Platform.

This module provides a unified result object for all internal components.
All modules must exchange results through this object to maintain consistency.
"""


class Result:
    """
    Unified result object for platform components.
    
    This is a behavior object, not just a data container.
    It encapsulates the result of an operation with success status,
    message, optional data, and optional error information.
    """

    def __init__(
        self,
        success: bool,
        message: str = "",
        data: dict | None = None,
        error: str | None = None,
    ):
        """
        Initialize a Result object.
        
        Args:
            success: Whether the operation was successful.
            message: Human-readable message describing the result.
            data: Optional dictionary with result data. Defaults to {} if None.
            error: Optional error code or identifier for failed operations.
        """
        self.success = success
        self.message = message
        self.data = {} if data is None else data
        self.error = error

    @classmethod
    def ok(cls, message: str = "", data: dict | None = None) -> "Result":
        """
        Create a successful result.
        
        Args:
            message: Human-readable success message.
            data: Optional dictionary with result data.
            
        Returns:
            A Result instance with success=True.
        """
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, error: str, message: str = "") -> "Result":
        """
        Create a failed result.
        
        Args:
            error: Error code or identifier.
            message: Human-readable error message.
            
        Returns:
            A Result instance with success=False.
        """
        return cls(success=False, message=message, error=error)

    def to_dict(self) -> dict:
        """
        Serialize the result to a dictionary.
        
        Always returns a dictionary with all four fields:
        success, message, data, error.
        
        Returns:
            A dictionary representation of the result.
        """
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "error": self.error,
        }
