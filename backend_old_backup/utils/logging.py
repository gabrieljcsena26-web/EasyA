"""Structured logging with correlation IDs."""
import logging
import json
import re
from datetime import datetime
from typing import Any, Dict
from contextvars import ContextVar
import uuid

# Context variable for correlation ID
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')


class StructuredFormatter(logging.Formatter):
    """JSON formatter that redacts PII."""
    
    PII_PATTERNS = [
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL]'),
        (re.compile(r'\b\+?[1-9]\d{1,14}\b'), '[PHONE]'),
        (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'), '[CARD]'),
    ]
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with PII redaction."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': self._redact_pii(record.getMessage()),
            'correlation_id': correlation_id_var.get(),
        }
        
        # Add extra fields
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)
    
    def _redact_pii(self, text: str) -> str:
        """Redact PII from text."""
        for pattern, replacement in self.PII_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


def setup_logging(level: str = 'INFO'):
    """Setup structured logging."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]
    
    # Reduce noise from third-party libraries
    logging.getLogger('motor').setLevel(logging.WARNING)
    logging.getLogger('pymongo').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def set_correlation_id(correlation_id: str = None):
    """Set correlation ID for current context."""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return correlation_id_var.get()
