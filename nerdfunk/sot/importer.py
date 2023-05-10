import logging
import json
import os
import yaml
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

    def open_file(self, filename):
        logging.debug(f'opening file {filename}')
        with open(filename) as f:
            try:
                content = yaml.safe_load(f.read())
            except Exception as exc:
                logging.error("could not read file %s; got exception %s" % (filename, exc))
                return None
        return content

    def import_data(self, data, title, creator):
        logging.debug("-- entering importer.py/import_data")
        self.open_nautobot()

        for item in data:
            if 'slug' in item:
                getter = {'slug': item.get('slug')}
            elif 'site' in item:
                getter = {'site': item.get('slsiteug')}
            else:
                getter = None
            success = self._sot.central.add_entity(creator, item)
            if success:
                logging.info(f'{title} successfully added to sot')
            else:
                logging.error(f'could not add {title} to sot')

    # -----===== user commands =====----- 

    def sites(self, *unnamed, **named):
        logging.debug("-- entering importer.py/sites")
        self.open_nautobot()
        properties = self.__convert_arguments_to_properties(*unnamed, **named)

        if 'file' in properties:
            content = self.open_file(properties['file'])
            self.import_data(content['sites'], "site", self._nautobot.dcim.sites)
        elif 'properties' in properties:
            self.import_data(properties['properties'], "site", self._nautobot.dcim.sites)

    def manufacturers(self, *unnamed, **named):
        logging.debug("-- entering importer.py/manufacturers")
        self.open_nautobot()
        properties = self.__convert_arguments_to_properties(*unnamed, **named)

        if 'file' in properties:
            content = self.open_file(properties['file'])
            self.import_data(content['manufacturers'], "manufacturer", self._nautobot.dcim.manufacturers)
        elif 'properties' in properties:
            self.import_data(properties['properties'], "manufacturer", self._nautobot.dcim.manufacturers)
    
    def platforms(self, *unnamed, **named):
        logging.debug("-- entering importer.py/platform")
        self.open_nautobot()
        properties = self.__convert_arguments_to_properties(*unnamed, **named)

        if 'file' in properties:
            content = self.open_file(properties['file'])
            self.import_data(content['platform'], "platform", self._nautobot.dcim.platforms)
        elif 'properties' in properties:
            self.import_data(properties['properties'], "platform", self._nautobot.dcim.platforms)
    
    def device_roles(self, *unnamed, **named):
        logging.debug("-- entering importer.py/device_roles")
        self.open_nautobot()
        properties = self.__convert_arguments_to_properties(*unnamed, **named)

        if 'file' in properties:
            content = self.open_file(properties['file'])
            self.import_data(content['device_roles'], "device_roles", self._nautobot.dcim.device_roles)
        elif 'properties' in properties:
            self.import_data(properties['properties'], "device_roles", self._nautobot.dcim.device_roles)

    def prefixes(self, *unnamed, **named):
        logging.debug("-- entering importer.py/prefixe")
        self.open_nautobot()
        properties = self.__convert_arguments_to_properties(*unnamed, **named)

        if 'file' in properties:
            content = self.open_file(properties['file'])
            self.import_data(content['prefixes'], "prefixes", self._nautobot.ipam.prefixes)
        elif 'properties' in properties:
            self.import_data(properties['properties'], "prefixes", self._nautobot.ipam.prefixes)

    def device_types(self, *unnamed, **named):
        logging.debug("-- entering importer.py/device_types")
        self.open_nautobot()
        properties = self.__convert_arguments_to_properties(*unnamed, **named)

        if 'file' in properties:
            content = self.open_file(properties['file'])
            self.import_data(content['device_types'], "device_types", self._nautobot.dcim.device_types)
        elif 'properties' in properties:
            self.import_data(properties['properties'], "device_types", self._nautobot.dcim.device_types)
