"""
Configuration Validator
Validates application configuration on startup
"""

import logging
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validate application configuration"""

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate application configuration

        Args:
            config: Configuration dictionary

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Validate database configuration
        db_config = config.get("database", {})
        
        # InfluxDB validation
        influx_config = db_config.get("influxdb", {})
        if influx_config.get("url"):
            token = influx_config.get("token", "")
            if token and token.startswith("${") and not os.getenv(token[2:-1]):
                errors.append(f"InfluxDB token environment variable not set: {token}")

        # PostgreSQL validation (optional)
        pg_config = db_config.get("postgresql", {})
        if pg_config.get("host"):
            pg_user = pg_config.get("user", "")
            pg_password = pg_config.get("password", "")
            if pg_user.startswith("${") and not os.getenv(pg_user[2:-1]):
                errors.append(f"PostgreSQL user environment variable not set: {pg_user}")
            if pg_password.startswith("${") and not os.getenv(pg_password[2:-1]):
                errors.append(f"PostgreSQL password environment variable not set: {pg_password}")

        # LLM configuration validation
        llm_config = config.get("llm", {})
        if llm_config.get("provider"):
            api_key = llm_config.get("api_key", "")
            if api_key.startswith("${") and not os.getenv(api_key[2:-1]):
                errors.append(f"LLM API key environment variable not set: {api_key}")

        # Grafana configuration validation (optional)
        grafana_config = config.get("grafana", {})
        if grafana_config.get("url"):
            api_key = grafana_config.get("api_key", "")
            if api_key.startswith("${") and not os.getenv(api_key[2:-1]):
                logger.warning(f"Grafana API key not set, Grafana features will be disabled")

        # Email configuration validation (optional)
        email_config = config.get("email", {})
        if email_config.get("smtp_host") and email_config.get("smtp_host") != "smtp.example.com":
            smtp_user = email_config.get("smtp_user", "")
            smtp_password = email_config.get("smtp_password", "")
            if smtp_user.startswith("${") and not os.getenv(smtp_user[2:-1]):
                errors.append(f"SMTP user environment variable not set: {smtp_user}")
            if smtp_password.startswith("${") and not os.getenv(smtp_password[2:-1]):
                errors.append(f"SMTP password environment variable not set: {smtp_password}")

        # Rule engine validation
        rule_engine_config = config.get("rule_engine", {})
        rules_file = rule_engine_config.get("rules_file", "config/rules.yaml")
        if rules_file:
            rules_path = Path(rules_file)
            if not rules_path.exists():
                errors.append(f"Rules file not found: {rules_file}")

        return len(errors) == 0, errors

    @staticmethod
    def validate_required_env_vars() -> tuple[bool, List[str]]:
        """
        Validate required environment variables

        Returns:
            Tuple of (is_valid, list_of_missing_vars)
        """
        missing = []
        
        # Check for critical environment variables
        # Note: These are optional, but we warn if they're missing
        critical_vars = [
            "INFLUXDB_TOKEN",  # Critical for data storage
        ]

        for var in critical_vars:
            if not os.getenv(var):
                missing.append(var)

        return len(missing) == 0, missing

    @staticmethod
    def validate_and_warn(config: Dict[str, Any]) -> bool:
        """
        Validate configuration and log warnings for missing optional items

        Args:
            config: Configuration dictionary

        Returns:
            True if configuration is valid (warnings are OK)
        """
        is_valid, errors = ConfigValidator.validate_config(config)
        
        if errors:
            logger.warning("Configuration validation found issues:")
            for error in errors:
                logger.warning(f"  - {error}")
            logger.warning("Some features may not work correctly")
        else:
            logger.info("Configuration validation passed")

        # Check environment variables
        env_valid, missing_env = ConfigValidator.validate_required_env_vars()
        if missing_env:
            logger.warning(f"Missing environment variables: {', '.join(missing_env)}")
            logger.warning("Some features may be disabled")

        return is_valid  # Return True even with warnings (non-critical)

