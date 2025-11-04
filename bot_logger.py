import logging
import os
from datetime import datetime
from functools import wraps
from typing import Optional, Callable
from discord.ext import commands

class BotLogger:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BotLogger, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance
    
    def _initialize_logger(self):
        """Initialize the logger with proper formatting and handlers."""
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger('disco_robo')
        self.logger.setLevel(logging.INFO)
        
        # Create handlers
        # File handler with year-month in filename for monthly rotation
        current_month = datetime.now().strftime('%Y-%m')
        file_handler = logging.FileHandler(
            filename=f'logs/disco_robo_{current_month}.log',
            encoding='utf-8',
            mode='a'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        
        # Create formatters and add it to handlers
        log_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(log_format)
        console_handler.setFormatter(log_format)
        
        # Add handlers to the logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    @classmethod
    def get_logger(cls):
        """Get the singleton logger instance."""
        if cls._instance is None:
            cls()
        return cls._instance.logger

def log_command():
    """Decorator for logging command usage."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = BotLogger.get_logger()
            ctx = args[0] if args else None
            
            if isinstance(ctx, commands.Context):
                # Log command invocation
                logger.info(
                    f"Command '{ctx.command}' used by {ctx.author} (ID: {ctx.author.id}) "
                    f"in {'DM' if ctx.guild is None else f'server {ctx.guild.name}'}"
                )
                
                try:
                    # Execute the command
                    result = await func(*args, **kwargs)
                    # Log successful execution
                    logger.info(f"Command '{ctx.command}' completed successfully")
                    return result
                except Exception as e:
                    # Log any exceptions
                    logger.error(
                        f"Error in command '{ctx.command}': {str(e)}",
                        exc_info=True
                    )
                    raise  # Re-raise the exception after logging
            else:
                return await func(*args, **kwargs)
        return wrapper
    return decorator

def log_event(event_name: Optional[str] = None):
    """Decorator for logging bot events."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = BotLogger.get_logger()
            event = event_name or func.__name__
            
            try:
                # Log event occurrence
                logger.info(f"Event '{event}' triggered")
                # Execute the event handler
                result = await func(*args, **kwargs)
                # Log successful handling
                logger.info(f"Event '{event}' handled successfully")
                return result
            except Exception as e:
                # Log any exceptions
                logger.error(f"Error in event '{event}': {str(e)}", exc_info=True)
                raise  # Re-raise the exception after logging
                
        return wrapper
    return decorator

def log_task(task_name: Optional[str] = None):
    """Decorator for logging scheduled tasks."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = BotLogger.get_logger()
            task = task_name or func.__name__
            
            try:
                # Log task start
                logger.info(f"Task '{task}' started")
                # Execute the task
                result = await func(*args, **kwargs)
                # Log successful completion
                logger.info(f"Task '{task}' completed successfully")
                return result
            except Exception as e:
                # Log any exceptions
                logger.error(f"Error in task '{task}': {str(e)}", exc_info=True)
                raise  # Re-raise the exception after logging
                
        return wrapper
    return decorator