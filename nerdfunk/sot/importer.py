import logging
import json
from pynautobot import api

class Importer(object):
    _sot = None
    _nautobot = None

    def __init__(self, sot):
        logging.debug(f'Creating IMPORTER object;')
        self._sot = sot

    def __getattr__(self, item):
        if item == "xxx":
            return self

    # -----===== internals =====----- 

    def open_nautobot(self):
        if self._nautobot is None:
            self._nautobot = api(self._sot.get_nautobot_url(), token=self._sot.get_token())
    
    def __convert_arguments_to_properties(self, *unnamed, **named):
        """ converts unnamed (dict) and named arguments to a single property dict """
        logging.debug("-- entering importer.py/__convert_arguments_to_properties")
        properties = {}
        nn = len(unnamed)
        for param in unnamed:
            if isinstance(param, dict):
                for key,value in param.items():
                    properties[key] = value
            elif isinstance(param, str):
                return param
            else:
                logging.error(f'cannot use paramater {param} / {type(param)} as value')
        for key,value in named.items():
                properties[key] = value
        
        return properties

    # -----===== user commands =====----- 

    def sites(self, *named, **unnamed):
        logging.debug("-- entering importer.py/sites")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)


    def manufacturers(self, *named, **unnamed):
        logging.debug("-- entering importer.py/manufacturers")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)


    def device_types(self, *named, **unnamed):
        logging.debug("-- entering importer.py/device_types")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)


    def device_roles(self, *named, **unnamed):
        logging.debug("-- entering importer.py/device_roles")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)


    def prefixe(self, *unnamed, **named):
        logging.debug("-- entering importer.py/prefixe")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)
        # print(json.dumps(properties, indent=4))
        print(properties)
