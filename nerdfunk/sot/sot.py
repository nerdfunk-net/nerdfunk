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
from . import messenger
from ..utilities import misc
from dotenv import load_dotenv, dotenv_values


class Sot:

    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    DEFAULT_FILENAME = "./config.yaml"

    def __init__(self, **named):
        # initialize variables
        self.__devices = {}
        self.__ipam = None
        self.__getter = None
        self.__importer = None
        self.__auth = None
        self.__central = None
        self.__messenger = None
        self._sot_config = None
        self._logs = []
        self._per_device = {}

        if 'filename' in named:
            filename = named['filename']
            del named['filename']
        else:
            filename = self.DEFAULT_FILENAME
            # read SOT config
            logging.debug("reading config %s/%s" % (self.BASEDIR, filename))
            self._sot_config = misc.read_config("%s/%s" % (self.BASEDIR, filename))
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
        if item == "messenger":
            if self.__messenger is None:
                self.__messenger = messenger.Messenger(self)
            return self.__messenger

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
        load_dotenv(os.path.join(self.BASEDIR, '.env'))

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

    def __convert_arguments_to_properties(self, *unnamed, **named):
        """ converts unnamed (dict) and named arguments to a single property dict """
        properties = {}
        if len(unnamed) > 0:
            for param in unnamed:
                print(param)
                if isinstance(param, dict):
                    for key,value in param.items():
                        properties[key] = value
                elif isinstance(param, str):
                    # it is just a text like log('something to log')
                    return param
                else:
                    logging.error(f'cannot use paramater {param} / {type(param)} as value')
        for key,value in named.items():
                properties[key] = value
        
        return properties

    def log(self, *unnamed, **named):
        # input is either a text like log('something to log')
        if len(unnamed) > 0 and isinstance (unnamed[0], str):
            properties = {'log': unnamed[0]}
        else:
            properties = self.__convert_arguments_to_properties(*unnamed, **named)

        if 'device' in properties:
            device = properties.get('device')
            if device not in self._per_device:
                self._per_device[device] = []
            self._per_device[device].append(properties.get('log'))
        else:
            self._logs.append(properties.get('log'))

    def get_logs(self, *unnamed, **named):
        properties = self.__convert_arguments_to_properties(*unnamed, **named)
        if 'device' in properties:
            return self._per_device.get(properties.get('device'))

        return self._logs, self._per_device
