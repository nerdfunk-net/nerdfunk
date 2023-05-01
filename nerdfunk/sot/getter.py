import logging
import requests
import json
from pynautobot import api
from . import git


class Getter(object):
    _instance = None
    _sot = None
    _nautobot = None
    _output_format = None

    def __new__(cls, sot):
        # we use a singleton pattern to ensure we have one
        # onboarding instance and not more
        if cls._instance is None:
            logging.debug(f'Creating GETTER object')
            cls._instance = super(Getter, cls).__new__(cls)
            # Put any initialization here
            cls._sot = sot
        return cls._instance

    def __getattr__(self, item):
        if item == "as_object" or item == "as_obj":
            self._output_format = "obj"
        elif item == "as_json":
            self._output_format = "json"
        elif item == "as_dict":
            self._output_format = "dict"
        return self

    def open_nautobot(self):
        if self._nautobot is None:
            self._nautobot = api(self._sot.get_nautobot_url(), token=self._sot.get_token())

    # -----===== user command =====-----

    def file(self, *unnamed, **named):
        logging.debug(f'-- entering getter.py/file')
        properties = dict(named)
        if unnamed:
            properties.update(unnamed[0])

        return git.get_file(self._sot.get_config(), properties)

    def device(self, *unnamed, **named):
        logging.debug("getting device from sot")

        if unnamed:
            for item in unnamed:
                if isinstance(item, str):
                    device_name = item
        if 'device' in named:
            getter = {'name': named.get('device')}
        elif 'ip' in named:
            ip_address = named.get('ip')
            getter = {'primary_ip4': named.get('ip')}

        self.open_nautobot()
        device = self._sot.central.get_entity(self._nautobot.dcim.devices, "Device", getter, getter)
        
        if self._output_format == "obj":
            return device
        elif self._output_format == "dict":
            return dict(device)
        elif self._output_format == "json":
            return json.dumps(device)
        else:
            return device

    def filter(self, **filter):
        logging.debug(f'getting filtered list of devices from sot using {filter}')

        self.open_nautobot()
        devices = self._nautobot.dcim.devices.filter(**filter)

        if self._output_format == "obj":
            return devices
        elif self._output_format == "dict":
            my_dict = {}
            for i in devices:
                my_dict[str(i)] = dict(i)
            return my_dict
        elif self._output_format == "json":
            my_dict = {}
            for i in devices:
                my_dict[str(i)] = dict(i)
            return json.dumps(my_dict)
        else:
            return devices

    def query(self, **unnamed):
        logging.debug(f'running graph ql query {unnamed}')
        query = None
        query_params = None

        if 'name' in unnamed:
            config = self._sot.get_config()
            query = config['nautobot'].get(unnamed['name'])
            if query is None:
                logging.error("unkown query %s" % unnamed['name'])
                return None
        if 'query_params' in unnamed:
            query_params = unnamed['query_params']

        self.open_nautobot()
        response = self._nautobot.graphql.query(query=query, variables=query_params).json
        
        if self._output_format == "obj":
            return response
        elif self._output_format == "dict":
            return dict(response)
        elif self._output_format == "json":
            return json.dumps(response)
        else:
            return response

    def hldm(self, **unnamed):
        logging.debug(f'getting HLDM of device {unnamed["device"]} from sot')
        return self.query(name='hldm', query_params={'name': '%s' % unnamed["device"]})