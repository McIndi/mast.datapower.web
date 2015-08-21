import threading
from time import sleep
from mast.logging import make_logger
from mast.timestamp import Timestamp
from gui import main


class Plugin(threading.Thread):
    def __init__(self):
        """Plugin is a SubClass of threading.Thread and is responsible for serving
        the Web GUI over https on the configured port"""
        logger = make_logger("mast.datapower.web")
        logger.debug("Initializing mastd.web plugin.")
        super(Plugin, self).__init__()
        self.daemon = True

    def run(self):
        logger = make_logger("web")
        logger.info("Attempting to serve web gui.")
        main()
        logger.info("web gui stopped")
