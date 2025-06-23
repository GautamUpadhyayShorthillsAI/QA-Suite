import logging
import os
import sys
from datetime import datetime
from pathlib import Path
import json
from typing import Optional, Dict, Any


class QASuiteLogger:
    """
    Comprehensive logging system for QA-Suite with CLI and file-based logging.
    Provides different log levels and formatted output for debugging.
    """

    def __init__(
        self, name: str = "QA-Suite", log_level: str = "INFO", log_to_file: bool = True
    ):
        self.name = name
        self.log_level = getattr(logging, log_level.upper())
        self.log_to_file = log_to_file

        # Create logs directory if it doesn't exist
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)

        # Initialize logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self.log_level)

        # Clear existing handlers
        self.logger.handlers.clear()

        # Add CLI handler with colored output
        self._setup_cli_handler()

        # Add file handler if requested
        if self.log_to_file:
            self._setup_file_handler()

    def _setup_cli_handler(self):
        """Setup CLI handler with colored output and custom formatting."""
        cli_handler = logging.StreamHandler(sys.stdout)
        cli_handler.setLevel(self.log_level)

        # Custom formatter with colors and timestamps
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        cli_handler.setFormatter(formatter)
        self.logger.addHandler(cli_handler)

    def _setup_file_handler(self):
        """Setup file handler for persistent logging."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.logs_dir / f"qa_suite_{timestamp}.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(self.log_level)

        # Detailed formatter for file logging
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        self.log_file_path = log_file

    def info(self, message: str, **kwargs):
        """Log info message with optional context."""
        if kwargs:
            message = f"{message} | Context: {json.dumps(kwargs, default=str)}"
        self.logger.info(message)

    def debug(self, message: str, **kwargs):
        """Log debug message with optional context."""
        if kwargs:
            message = f"{message} | Context: {json.dumps(kwargs, default=str)}"
        self.logger.debug(message)

    def warning(self, message: str, **kwargs):
        """Log warning message with optional context."""
        if kwargs:
            message = f"{message} | Context: {json.dumps(kwargs, default=str)}"
        self.logger.warning(message)

    def error(self, message: str, **kwargs):
        """Log error message with optional context."""
        if kwargs:
            message = f"{message} | Context: {json.dumps(kwargs, default=str)}"
        self.logger.error(message)

    def critical(self, message: str, **kwargs):
        """Log critical message with optional context."""
        if kwargs:
            message = f"{message} | Context: {json.dumps(kwargs, default=str)}"
        self.logger.critical(message)

    def step(self, step_name: str, step_number: int, total_steps: int, **kwargs):
        """Log a workflow step with progress information."""
        progress = f"[{step_number}/{total_steps}]"
        message = f"STEP {progress} {step_name}"
        if kwargs:
            message = f"{message} | Context: {json.dumps(kwargs, default=str)}"
        self.logger.info(message)

    def api_call(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float = None,
        **kwargs,
    ):
        """Log API call details."""
        message = f"API {method} {endpoint} | Status: {status_code}"
        if response_time:
            message = f"{message} | Time: {response_time:.2f}s"
        if kwargs:
            message = f"{message} | Context: {json.dumps(kwargs, default=str)}"
        self.logger.info(message)

    def test_result(
        self, test_name: str, result: str, duration: float = None, **kwargs
    ):
        """Log test execution results."""
        message = f"TEST {test_name} | Result: {result}"
        if duration:
            message = f"{message} | Duration: {duration:.2f}s"
        if kwargs:
            message = f"{message} | Context: {json.dumps(kwargs, default=str)}"
        self.logger.info(message)

    def file_operation(self, operation: str, file_path: str, success: bool, **kwargs):
        """Log file operations."""
        status = "SUCCESS" if success else "FAILED"
        message = f"FILE {operation} {file_path} | Status: {status}"
        if kwargs:
            message = f"{message} | Context: {json.dumps(kwargs, default=str)}"
        self.logger.info(message)

    def user_action(self, action: str, **kwargs):
        """Log user actions in the UI."""
        message = f"USER ACTION: {action}"
        if kwargs:
            message = f"{message} | Context: {json.dumps(kwargs, default=str)}"
        self.logger.info(message)

    def performance(self, operation: str, duration: float, **kwargs):
        """Log performance metrics."""
        message = f"PERFORMANCE {operation} | Duration: {duration:.2f}s"
        if kwargs:
            message = f"{message} | Context: {json.dumps(kwargs, default=str)}"
        self.logger.info(message)

    def get_log_file_path(self) -> Optional[str]:
        """Get the path to the current log file."""
        return str(self.log_file_path) if hasattr(self, "log_file_path") else None


# Global logger instance
qa_logger = QASuiteLogger()


def get_logger(name: str = None) -> QASuiteLogger:
    """Get a logger instance. If name is provided, creates a child logger."""
    if name:
        return QASuiteLogger(name=name)
    return qa_logger


# Convenience functions for quick logging
def log_info(message: str, **kwargs):
    qa_logger.info(message, **kwargs)


def log_debug(message: str, **kwargs):
    qa_logger.debug(message, **kwargs)


def log_warning(message: str, **kwargs):
    qa_logger.warning(message, **kwargs)


def log_error(message: str, **kwargs):
    qa_logger.error(message, **kwargs)


def log_step(step_name: str, step_number: int, total_steps: int, **kwargs):
    qa_logger.step(step_name, step_number, total_steps, **kwargs)


def log_api_call(
    endpoint: str, method: str, status_code: int, response_time: float = None, **kwargs
):
    qa_logger.api_call(endpoint, method, status_code, response_time, **kwargs)


def log_test_result(test_name: str, result: str, duration: float = None, **kwargs):
    qa_logger.test_result(test_name, result, duration, **kwargs)


def log_file_operation(operation: str, file_path: str, success: bool, **kwargs):
    qa_logger.file_operation(operation, file_path, success, **kwargs)


def log_user_action(action: str, **kwargs):
    qa_logger.user_action(action, **kwargs)


def log_performance(operation: str, duration: float, **kwargs):
    qa_logger.performance(operation, duration, **kwargs)
