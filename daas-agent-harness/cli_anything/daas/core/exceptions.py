"""DAAS exception classes."""


class DAASError(Exception):
    """Base exception for all DAAS errors."""
    pass


class SourceUnavailableError(DAASError):
    """Raised when a data source is unreachable (API down, no internet, etc.)."""

    def __init__(self, source: str, detail: str = ""):
        self.source = source
        self.detail = detail
        super().__init__(f"Source '{source}' is unavailable{f': {detail}' if detail else ''}")


class FunctionNotFoundError(DAASError):
    """Raised when a requested function doesn't exist in any source."""

    def __init__(self, function_name: str):
        self.function_name = function_name
        super().__init__(f"Function '{function_name}' not found in any source")


class ParameterError(DAASError):
    """Raised when function parameters are invalid or missing."""

    def __init__(self, function_name: str, detail: str = ""):
        self.function_name = function_name
        self.detail = detail
        super().__init__(f"Parameter error for '{function_name}'{f': {detail}' if detail else ''}")
