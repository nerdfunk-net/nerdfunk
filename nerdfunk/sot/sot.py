import logging
import os
import json
from . import device
from . import ipam
from . import getter
from . import device
from . import central
from . import importer
from . import auth
from ..utilities import misc
from dotenv import load_dotenv, dotenv_values


BASEDIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_FILENAME = "./config.yaml"

class Sot:
    _instance = None
    __devices = {}
    __ipam = None
    __getter = None
    __importer = None
    __auth = None
    __central = None
    _sot_config = None

    def __init__(self, **named):
        if 'filename' in named:
            filename = named['filename']
            del named['filename']
        else:
            filename = DEFAULT_FILENAME
            # read SOT config
            logging.debug("reading config %s/%s" % (BASEDIR, filename))
            self._sot_config = misc.read_config("%s/%s" % (BASEDIR, filename))
            self._sot_config['nautobot'].update(named)

    def __getattr__(self, item):
        if item == "ipam":
            if self.__ipam is None:
                self.__ipam = ipam.Ipam(self)
            return self.__ipam
        if item == "get":
            if self.__getter is None:
                self.__getter = getter.Getter(self)
            return self.__getter
        if item == "central":
            if self.__central is None:
                self.__central = central.Central(self)
            return self.__central
        if item == "importer":
            if self.__importer is None:
                self.__importer = importer.Importer(self)
            return self.__importer
        if item == "auth":
            if self.__auth is None:
                self.__auth = auth.Auth(self)
            return self.__auth

    def get_token(self):
        return self._sot_config['nautobot']['token']

    def get_nautobot_url(self):
        return self._sot_config['nautobot']['url']

    def get_config(self):
        return self._sot_config

    def device(self, name):
        if name not in self.__devices:
            self.__devices[name] = device.Device(self, name)
        return self.__devices[name]

    def auth(self, **named):
        parameter = dict(named)
        # Get the path to the directory this file is in
        BASEDIR = os.path.abspath(os.path.dirname(__file__))
        # Connect the path with the '.env' file name
        load_dotenv(os.path.join(BASEDIR, '.env'))

        salt = named.get('salt')
        if salt is None:
            logging.debug(f'using default salt from .env')
            parameter['salt'] = os.getenv('SALT')

        encryption_key = named.get('encryption_key')
        if encryption_key is None:
            logging.debug(f'using default encryption_key from .env')
            parameter['encryption_key'] = os.getenv('ENCRYPTIONKEY')

        iterations = named.get('iterations')
        if iterations is None:
            logging.debug(f'using default iterations from .env')
            parameter['iterations'] = int(os.getenv('ITERATIONS'))

        logging.debug(f'salt: {salt} encryption_key: {encryption_key}')
        if self.__auth is None:
            self.__auth = auth.Auth(self, **parameter)
        return self.__auth
