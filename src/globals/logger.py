import logging


COLOR_MAP = {
    'DEBUG': '\033[94m',
    'INFO': '\033[92m',
    'WARNING': '\033[93m',
    'ERROR': '\033[91m',
    'CRITICAL': '\033[95m'
}
RESET_CODE = '\033[0m'


def colorize(message, level):

    color = COLOR_MAP.get(level, RESET_CODE)
    return f'{color}{message}{RESET_CODE}'


class ColorFilter(logging.Filter):
    def filter(self, record):

        record.msg = colorize(record.msg, record.levelname)
        return True


def setup_logger(file_name):
    logger = logging.getLogger(file_name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)'
        )

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)

        stream_handler.addFilter(ColorFilter())
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger
