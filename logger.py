import logging

def get_logger(name: str = "legal_automation") -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(logging.INFO)
    return logger

# Example global logger instance
logger = get_logger()
