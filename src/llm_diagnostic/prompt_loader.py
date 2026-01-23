"""
Flexible Prompt Template Loader
Supports Jinja2 templates with dynamic template selection
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

logger = logging.getLogger(__name__)


class PromptLoader:
    """
    Flexible prompt template loader
    Supports multiple template directories and dynamic template selection
    """

    def __init__(self, template_dirs: Optional[list] = None, default_template: Optional[str] = None):
        """
        Initialize prompt loader

        Args:
            template_dirs: List of template directory paths (default: ['prompts'])
            default_template: Default template name if specific template not found
        """
        if template_dirs is None:
            # Default to prompts/ directory in project root
            project_root = Path(__file__).parent.parent.parent
            template_dirs = [str(project_root / "prompts")]

        self.template_dirs = [Path(d) for d in template_dirs]
        self.default_template = default_template or "default.j2"

        # Create Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader([str(d) for d in self.template_dirs]),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self.env.filters["join"] = lambda items, sep=", ": sep.join(str(item) for item in items)

    def load(self, template_name: str) -> Any:
        """
        Load template by name

        Args:
            template_name: Template name (e.g., 'cell_voltage_deviation' or 'cell_voltage_deviation.j2')

        Returns:
            Jinja2 Template object
        """
        # Add .j2 extension if not present
        if not template_name.endswith(".j2"):
            template_name = f"{template_name}.j2"

        try:
            template = self.env.get_template(template_name)
            logger.debug(f"Loaded template: {template_name}")
            return template
        except TemplateNotFound:
            logger.warning(f"Template not found: {template_name}, trying default template")
            if self.default_template:
                try:
                    return self.env.get_template(self.default_template)
                except TemplateNotFound:
                    logger.error(f"Default template also not found: {self.default_template}")
                    raise
            raise

    def render(
        self, template_name: str, context: Dict[str, Any], fallback_to_default: bool = True
    ) -> str:
        """
        Render template with context

        Args:
            template_name: Template name
            context: Template context variables
            fallback_to_default: Whether to fallback to default template if not found

        Returns:
            Rendered prompt string
        """
        try:
            template = self.load(template_name)
            return template.render(**context)
        except TemplateNotFound:
            if fallback_to_default and self.default_template:
                logger.warning(f"Using default template: {self.default_template}")
                template = self.load(self.default_template)
                return template.render(**context)
            raise

    def get_template_name(self, alarm_type: str, device_type: Optional[str] = None) -> str:
        """
        Get template name from alarm type and device type
        Flexible naming convention: {alarm_type}.j2 or {device_type}_{alarm_type}.j2

        Args:
            alarm_type: Alarm type (e.g., 'cell_voltage_deviation')
            device_type: Optional device type (e.g., 'BMS', 'PCS')

        Returns:
            Template name
        """
        # Try device-specific template first
        if device_type:
            template_name = f"{device_type.lower()}_{alarm_type}"
            template_path = f"{template_name}.j2"
            # Check if template exists
            for template_dir in self.template_dirs:
                if (template_dir / template_path).exists():
                    return template_name

        # Fallback to alarm type template
        return alarm_type

    def list_templates(self) -> list:
        """List all available templates"""
        templates = []
        for template_dir in self.template_dirs:
            if template_dir.exists():
                templates.extend(
                    [
                        f.stem
                        for f in template_dir.glob("*.j2")
                        if f.is_file()
                    ]
                )
        return sorted(set(templates))

    def add_template_dir(self, template_dir: str):
        """
        Add additional template directory

        Args:
            template_dir: Path to template directory
        """
        template_path = Path(template_dir)
        if template_path.exists():
            self.template_dirs.append(template_path)
            # Recreate environment with new loader
            self.env = Environment(
                loader=FileSystemLoader([str(d) for d in self.template_dirs]),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            logger.info(f"Added template directory: {template_dir}")
        else:
            logger.warning(f"Template directory does not exist: {template_dir}")

