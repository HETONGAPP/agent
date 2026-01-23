"""
Email Service Module
Flexible email service for alarm notifications with diagnostic reports
Supports multiple SMTP providers and email services
"""

from .client import EmailClient, SMTPConfig
from .template import EmailTemplateEngine
from .service import EmailService
from .queue import EmailQueue

__all__ = [
    "EmailClient",
    "SMTPConfig",
    "EmailTemplateEngine",
    "EmailService",
    "EmailQueue",
]


