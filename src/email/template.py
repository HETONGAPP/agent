"""
Email Template Engine
Flexible template system for email content generation
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)


class EmailTemplateEngine:
    """
    Flexible email template engine
    Supports HTML and plain text templates
    """

    def __init__(self, template_dirs: Optional[list] = None):
        """
        Initialize template engine

        Args:
            template_dirs: List of template directory paths (default: ['templates/email'])
        """
        if template_dirs is None:
            # Default to templates/email directory in project root
            project_root = Path(__file__).parent.parent.parent
            template_dirs = [str(project_root / "templates" / "email")]

        self.template_dirs = [Path(d) for d in template_dirs]

        # Create Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader([str(d) for d in self.template_dirs]),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self.env.filters["markdown"] = self._markdown_filter

    def render(
        self,
        template_name: str,
        context: Dict[str, Any],
        template_type: str = "html",
    ) -> tuple[str, str]:
        """
        Render email template

        Args:
            template_name: Template name (without extension)
            context: Template context variables
            template_type: Template type ('html' or 'text')

        Returns:
            Tuple of (html_content, text_content)
        """
        html_content = None
        text_content = None

        # Try to load HTML template
        html_template_name = f"{template_name}.html.j2"
        try:
            html_template = self.env.get_template(html_template_name)
            html_content = html_template.render(**context)
        except Exception as e:
            logger.debug(f"HTML template not found or error: {e}")

        # Try to load text template
        text_template_name = f"{template_name}.txt.j2"
        try:
            text_template = self.env.get_template(text_template_name)
            text_content = text_template.render(**context)
        except Exception as e:
            logger.debug(f"Text template not found or error: {e}")

        # If no templates found, generate default content
        if not html_content and not text_content:
            logger.warning(f"No templates found for {template_name}, using default")
            html_content, text_content = self._generate_default_content(context)

        # If only one template found, generate the other from it
        if html_content and not text_content:
            text_content = self._html_to_text(html_content)
        elif text_content and not html_content:
            html_content = self._text_to_html(text_content)

        return html_content or "", text_content or ""

    def _generate_default_content(self, context: Dict[str, Any]) -> tuple[str, str]:
        """Generate default email content"""
        alarm = context.get("alarm", {})
        diagnostic = context.get("diagnostic", {})

        subject = context.get("subject", "BESS Alarm Notification")
        alarm_type = alarm.get("alarm_type", "Unknown")
        severity = alarm.get("severity", "Warning")
        risk_level = diagnostic.get("risk_level", "Low")

        html = f"""
        <html>
        <body>
            <h2>BESS Alarm Notification</h2>
            <p><strong>Alarm Type:</strong> {alarm_type}</p>
            <p><strong>Severity:</strong> {severity}</p>
            <p><strong>Risk Level:</strong> {risk_level}</p>
            <p><strong>Status:</strong> {diagnostic.get('current_status', 'N/A')}</p>
        </body>
        </html>
        """

        text = f"""
BESS Alarm Notification

Alarm Type: {alarm_type}
Severity: {severity}
Risk Level: {risk_level}
Status: {diagnostic.get('current_status', 'N/A')}
        """

        return html.strip(), text.strip()

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text (simple implementation)"""
        import re

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", html)
        # Decode HTML entities
        text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _text_to_html(self, text: str) -> str:
        """Convert plain text to HTML"""
        # Simple conversion: preserve line breaks
        html = text.replace("\n", "<br>\n")
        return f"<html><body>{html}</body></html>"

    def _markdown_filter(self, text: str) -> str:
        """Convert Markdown to HTML (simple implementation)"""
        import re

        # Headers
        text = re.sub(r"^### (.*)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
        text = re.sub(r"^## (.*)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
        text = re.sub(r"^# (.*)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)

        # Bold
        text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)

        # Italic
        text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)

        # Links
        text = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r'<a href="\2">\1</a>', text)

        # Lists
        text = re.sub(r"^\d+\. (.*)$", r"<li>\1</li>", text, flags=re.MULTILINE)
        text = re.sub(r"^- (.*)$", r"<li>\1</li>", text, flags=re.MULTILINE)

        # Line breaks
        text = text.replace("\n", "<br>\n")

        return text

    def add_template_dir(self, template_dir: str):
        """
        Add additional template directory

        Args:
            template_dir: Path to template directory
        """
        template_path = Path(template_dir)
        if template_path.exists():
            self.template_dirs.append(template_path)
            # Recreate environment
            self.env = Environment(
                loader=FileSystemLoader([str(d) for d in self.template_dirs]),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            self.env.filters["markdown"] = self._markdown_filter
            logger.info(f"Added template directory: {template_dir}")
        else:
            logger.warning(f"Template directory does not exist: {template_dir}")


