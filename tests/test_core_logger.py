import app.core.logger as logger_module


def test_get_logger_returns_configured_module_logger():
    assert logger_module.get_logger() is logger_module.logger
