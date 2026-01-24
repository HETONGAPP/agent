"""
Debug utility module
Provides functions for controlled debug output based on DEBUG environment variable
"""

import os
import logging

# Check DEBUG mode from environment variable
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes", "on")

def debug_print(*args, **kwargs):
    """
    Print debug message only if DEBUG mode is enabled
    
    Args:
        *args: Arguments to print
        **kwargs: Keyword arguments for print()
    """
    if DEBUG_MODE:
        print(*args, **kwargs)

def debug_warning(message, *args, **kwargs):
    """
    Log warning message only if DEBUG mode is enabled
    
    Args:
        message: Warning message
        *args: Additional arguments for logger.warning()
        **kwargs: Keyword arguments for logger.warning()
    """
    if DEBUG_MODE:
        logger = logging.getLogger(__name__)
        logger.warning(message, *args, **kwargs)

def is_debug_mode():
    """
    Check if DEBUG mode is enabled
    
    Returns:
        bool: True if DEBUG mode is enabled, False otherwise
    """
    return DEBUG_MODE



