import logging
import os
from . import device
from . import ipam
from . import getter
from . import device
from . import central
from ..utilities import misc


BASEDIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_FILENAME = "./config.yaml"

class Sot:
    _instance = None
    __devices = {}
    __ipam = None
    __getter = None
    __central = None
    _sot_config = None

    def __new__(cls, filename=DEFAULT_FILENAME):
        # we use a singleton pattern to ensure we have one
        # onboarding instance and not more
        if cls._instance is None:
            logging.debug(f'Creating SOT object')
            cls._instance = super(Sot, cls).__new__(cls)
            # read SOT config
            logging.debug("reading config %s/%s" % (BASEDIR, filename))
            cls._sot_config = misc.read_config("%s/%s" % (BASEDIR, filename))
        return cls._instance

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

    def get_token(self):
        return self._sot_config['nautobot']['token']

    def get_nautobot_url(self):
        return self._sot_config['nautobot']['url']

    def get_config(self):
        return self._sot_config

    def device(self, name):
        if name not in self.__devices:
            logging.debug(f'init device {name}')
            self.__devices[name] = device.Device(self, name)
        return self.__devices[name]


