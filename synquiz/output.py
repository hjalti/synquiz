import logging

class ColorFormatter(logging.Formatter):
    FORMATS = {
        logging.ERROR: "\033[1m\033[91m[-] %(msg)s\033[00m",
        logging.WARNING: "\033[1m\033[93m[+] %(msg)s\033[00m",
        logging.INFO: "\033[92m[*] %(msg)s\033[00m",
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, "[+] %(msg)s")
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def setup_logger(level=logging.DEBUG):
    logger = logging.getLogger('synquiz')
    logger.setLevel(level)
    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(ColorFormatter())
    logger.addHandler(sh)
