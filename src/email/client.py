"""
Flexible Email Client
Supports SMTP and various email service providers
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)


class SMTPConfig:
    """SMTP configuration"""

    def __init__(
        self,
        host: str,
        port: int = 587,
        user: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
        use_ssl: bool = False,
    ):
        """
        Initialize SMTP configuration

        Args:
            host: SMTP server host
            port: SMTP server port
            user: SMTP username
            password: SMTP password
            use_tls: Use TLS encryption
            use_ssl: Use SSL encryption
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl


class EmailClient:
    """
    Flexible email client
    Supports SMTP and can be extended for other email services
    """

    def __init__(self, config: SMTPConfig):
        """
        Initialize email client

        Args:
            config: SMTP configuration
        """
        self.config = config

    def send(
        self,
        from_address: str,
        to_addresses: List[str],
        subject: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Send email synchronously

        Args:
            from_address: Sender email address
            to_addresses: List of recipient email addresses
            subject: Email subject
            body_text: Plain text body
            body_html: HTML body
            cc_addresses: Optional CC addresses
            bcc_addresses: Optional BCC addresses
            attachments: Optional attachments list [{"filename": "...", "content": b"...", "content_type": "..."}]

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = from_address
            msg["To"] = ", ".join(to_addresses)
            msg["Subject"] = subject

            if cc_addresses:
                msg["Cc"] = ", ".join(cc_addresses)

            # Add body
            if body_text:
                msg.attach(MIMEText(body_text, "plain", "utf-8"))
            if body_html:
                msg.attach(MIMEText(body_html, "html", "utf-8"))

            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.get("content", b""))
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{attachment.get("filename", "attachment")}"',
                    )
                    msg.attach(part)

            # Connect to SMTP server
            if self.config.use_ssl:
                server = smtplib.SMTP_SSL(self.config.host, self.config.port)
            else:
                server = smtplib.SMTP(self.config.host, self.config.port)
                if self.config.use_tls:
                    server.starttls()

            # Login if credentials provided
            if self.config.user and self.config.password:
                server.login(self.config.user, self.config.password)

            # Send email
            recipients = to_addresses.copy()
            if cc_addresses:
                recipients.extend(cc_addresses)
            if bcc_addresses:
                recipients.extend(bcc_addresses)

            server.sendmail(from_address, recipients, msg.as_string())
            server.quit()

            logger.info(f"Email sent successfully to {len(to_addresses)} recipient(s)")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            return False

    async def send_async(
        self,
        from_address: str,
        to_addresses: List[str],
        subject: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Send email asynchronously

        Args:
            Same as send() method

        Returns:
            True if sent successfully, False otherwise
        """
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.send,
            from_address,
            to_addresses,
            subject,
            body_text,
            body_html,
            cc_addresses,
            bcc_addresses,
            attachments,
        )

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "EmailClient":
        """
        Create email client from configuration

        Args:
            config: Email configuration from app.yaml

        Returns:
            EmailClient instance
        """
        smtp_config = SMTPConfig(
            host=config.get("smtp_host", "smtp.example.com"),
            port=config.get("smtp_port", 587),
            user=config.get("smtp_user"),
            password=config.get("smtp_password"),
            use_tls=config.get("smtp_use_tls", True),
            use_ssl=config.get("smtp_use_ssl", False),
        )
        return cls(smtp_config)


