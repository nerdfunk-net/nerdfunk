import logging
import requests
import json


class Messenger(object):

    def __new__(cls, sot):
        cls._instance = None
        cls._sot = None

        # singleton
        if cls._instance is None:
            logging.debug(f'Creating MESSENGER object')
            cls._instance = super(Messender, cls).__new__(cls)
            # Put any initialization here
            cls._sot = sot
        return cls._instance
