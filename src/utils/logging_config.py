"""
Unified logging configuration for Uvicorn format
All modules should use this configuration for consistent log formatting
Preserves Uvicorn's default colored output
"""

import os
import logging

# Global debug mode flag - can be set via environment variable DEBUG=true/false
# When DEBUG=true: Only show WARNING and above (hide INFO and DEBUG logs)
# When DEBUG=false: Show INFO and above (normal operation)
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes", "on")

# Export for use in other modules
__all__ = ["DEBUG_MODE", "configure_uvicorn_logging"]


class WebSocketConnectionFilter(logging.Filter):
    """Filter to hide WebSocket connection messages"""
    def filter(self, record):
        # Completely hide WebSocket connection messages
        # Uvicorn access logger format: "('127.0.0.1', 51764) - \"WebSocket /ws\" [accepted]"
        # or just "connection open"
        
        # Get the message - try multiple ways
        msg = ''
        try:
            msg = str(record.getMessage())
        except:
            try:
                msg = str(record.msg)
            except:
                msg = ''
        
        # Also check args if available (for formatted messages)
        if hasattr(record, 'args') and record.args:
            args_str = ' '.join(str(arg) for arg in record.args)
            msg = f"{msg} {args_str}"
        
        # Get raw record.msg - this is the unformatted message template
        # Uvicorn might use formatted messages, so check record.msg directly
        record_msg = getattr(record, 'msg', '')
        record_msg_str = str(record_msg) if record_msg else ''
        
        # Convert to lowercase for case-insensitive matching
        msg_lower = msg.lower()
        record_msg_lower = record_msg_str.lower()
        
        # Check for WebSocket patterns - check both formatted message and raw record.msg
        # Uvicorn might log WebSocket messages in different formats
        
        # Pattern 1: "connection open" or "connection closed"
        # Check both formatted message and raw record.msg
        # Raw format: 'connection open' or 'connection closed'
        if ('connection open' in msg_lower or 'connection closed' in msg_lower or
            'connection open' in record_msg_lower or 'connection closed' in record_msg_lower):
            return False
        
        # Pattern 2: WebSocket /ws with [accepted] - check both formatted and raw
        # Formatted format: "('127.0.0.1', 59324) - \"WebSocket /ws\" [accepted]"
        # Raw format: '%s - "WebSocket %s" [accepted]'
        if (('websocket' in msg_lower and ('/ws' in msg_lower or '[accepted]' in msg_lower)) or
            ('websocket' in record_msg_lower and ('/ws' in record_msg_lower or '[accepted]' in record_msg_lower))):
            return False
        
        # Pattern 3: Check for WebSocket template format in record.msg
        # Format: '%s - "WebSocket %s" [accepted]'
        if record_msg_str and isinstance(record_msg_str, str):
            if '"WebSocket %s"' in record_msg_str or '"websocket %s"' in record_msg_lower:
                if '[accepted]' in record_msg_str or '[accepted]' in record_msg_lower:
                    return False
        
        # Pattern 4: Just /ws path with accepted in formatted message
        if '/ws' in msg_lower and ('accepted' in msg_lower or 'websocket' in msg_lower):
            return False
        
        # Pattern 6: Check for tuple format in formatted message
        # Format: "('127.0.0.1', 59324) - \"WebSocket /ws\" [accepted]"
        if msg and isinstance(msg, str):
            # Check if message contains tuple pattern with WebSocket
            if '(' in msg and ')' in msg and 'websocket' in msg_lower and '[accepted]' in msg_lower:
                return False
        
        # Pattern 7: Check record attributes
        if hasattr(record, 'path') and record.path == '/ws':
            return False
        
        # Pattern 8: Check if it's a WebSocket upgrade request
        if hasattr(record, 'scope'):
            scope = record.scope
            if isinstance(scope, dict) and scope.get('type') == 'websocket':
                return False
        
        # Pattern 9: Check message format directly (case-sensitive for exact match)
        # Format: "('127.0.0.1', 50490) - \"WebSocket /ws\" [accepted]"
        if ('"WebSocket /ws"' in msg or '"websocket /ws"' in msg_lower or
            '"WebSocket /ws"' in record_msg_str or '"websocket /ws"' in record_msg_str.lower()):
            return False
        
        return True  # Show other logs


def configure_uvicorn_logging():
    """
    Configure application loggers to use Uvicorn's colored format
    
    This function should be called AFTER Uvicorn has started and configured
    its own colored logging. It ensures all application modules use the
    same format and colors as Uvicorn.
    
    Uvicorn format: "INFO:     message" (with colors)
    - INFO: green
    - WARNING: yellow  
    - ERROR: red
    - DEBUG: blue/gray
    """
    # Get uvicorn loggers - WebSocket logs might come from different loggers
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_protocols_ws_logger = logging.getLogger("uvicorn.protocols.websockets")
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    
    # Create and add filter to hide WebSocket connection messages
    ws_filter = WebSocketConnectionFilter()
    
    # Apply filter to all uvicorn loggers that might log WebSocket messages
    for logger in [uvicorn_access_logger, uvicorn_protocols_ws_logger, uvicorn_error_logger]:
        logger.addFilter(ws_filter)
        # Also apply to all handlers
        for handler in list(logger.handlers):
            if ws_filter not in handler.filters:
                handler.addFilter(ws_filter)
    
    # Also check root logger handlers (uvicorn might use these)
    root_logger = logging.getLogger()
    root_logger.addFilter(ws_filter)
    root_handlers_to_update = list(root_logger.handlers)
    for handler in root_handlers_to_update:
        if ws_filter not in handler.filters:
            handler.addFilter(ws_filter)
    
    # Monkey-patch addHandler to automatically add filter to new handlers
    # This ensures the filter works even if uvicorn reconfigures handlers later
    if not hasattr(uvicorn_access_logger, '_original_addHandler'):
        uvicorn_access_logger._original_addHandler = uvicorn_access_logger.addHandler
        def addHandler_with_filter(handler):
            if ws_filter not in handler.filters:
                handler.addFilter(ws_filter)
            return uvicorn_access_logger._original_addHandler(handler)
        uvicorn_access_logger.addHandler = addHandler_with_filter
    
    # Also monkey-patch root logger
    if not hasattr(root_logger, '_original_addHandler'):
        root_logger._original_addHandler = root_logger.addHandler
        def root_addHandler_with_filter(handler):
            if ws_filter not in handler.filters:
                handler.addFilter(ws_filter)
            return root_logger._original_addHandler(handler)
        root_logger.addHandler = root_addHandler_with_filter
    
    # Set log level based on DEBUG mode
    # DEBUG=true: Show all logs including INFO and WARNING (detailed debugging)
    # DEBUG=false: Only show ERROR and above (hide INFO and WARNING for cleaner output)
    if DEBUG_MODE:
        app_log_level = logging.INFO  # Show INFO, WARNING, ERROR, CRITICAL (all logs)
        print(f"[LoggingConfig] DEBUG mode ENABLED - Showing all logs (INFO, WARNING, ERROR)")
    else:
        app_log_level = logging.ERROR  # Only show ERROR, CRITICAL (hide INFO and WARNING)
        print(f"[LoggingConfig] DEBUG mode DISABLED - Showing ERROR and above only (hiding INFO and WARNING)")
    
    # Configure all application loggers to propagate to uvicorn logger
    # This makes them use Uvicorn's colored format automatically
    for logger_name in [
        "src",
        "src.agent",
        "src.mqtt",
        "src.core",
        "src.storage",
        "src.llm_diagnostic",
        "src.grafana",
        "src.email",
        "src.rule_engine",
        "src.integrations",
        "src.diagnostic_agent",  # Add diagnostic agent loggers
    ]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(app_log_level)
        # Remove any existing handlers to avoid duplicate logs
        logger.handlers = []
        # Propagate to root logger (which Uvicorn has configured with colors)
        logger.propagate = True

