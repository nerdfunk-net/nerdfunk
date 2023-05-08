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
    _cache = {'site':{}, 'vlan': {} }

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

    def _get_vlan(self, vid, site):
        logging.debug("-- entering sot/getter.py/_get_vlan")
        logging.debug(f'getting vlan: {vid} / {site}')
        self.open_nautobot()

        vlans = self._nautobot.ipam.vlans.filter(vid=vid)
        for vlan in vlans:
            try:
                site_name = vlan.site.name
            except Exception:
                site_name = None

            if site_name == site:
                return vlan

        logging.debug("no VLAN found")
        return None

    # -----===== user command =====-----

    def file(self, *unnamed, **named):
        logging.debug(f'-- entering getter.py/file')
        properties = dict(named)
        if unnamed:
            properties.update(unnamed[0])

        return git.get_file(self._sot.get_config(), properties)

    def device(self, *unnamed, **named):
        logging.debug("getting device from sot")
        self.open_nautobot()
        getter = None

        if unnamed:
            for item in unnamed:
                if isinstance(item, str):
                    device_name = item
        if 'device' in named:
            getter = {'name': named.get('device')}
        elif 'ip' in named:
            response = self.query(name='device_properties_by_cidr', 
                                query_params={'cidr': named.get('ip')})
            if len(response['data']['ip_addresses']) > 0:
                if response['data']['ip_addresses'][0]['primary_ip4_for'] is None:
                    logging.debug("device %s not found in sot" % named.get('ip'))
                    return None
                getter = {'name': response['data']['ip_addresses'][0]['primary_ip4_for']['hostname']}
            else:
                logging.debug("device %s not found in sot" % named.get('ip'))
                return None

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
    
    def id(self, **named):
        self.open_nautobot()
        item = named.get('item')
        del named['item']
        logging.debug(f'getting id of {item}; parameter {named}')

        if item == "site":
            site_name = named.get('name')
            if site_name in self._cache['site']:
                logging.debug(f'getting id from cache')
                return self._cache['site'][site_name]
            try:
                site = self._nautobot.dcim.sites.get(**named)
                if site:
                    logging.debug(f'adding {site.id} to cache')
                    self._cache['site'][site_name] = site.id
                else:
                    logging.error(f'unknown site {site_name}')
            except Exception as exc:
                logging.error(f'got exception {exc}')
                return None
        elif item =="vlan":
            vid = named.get('vid')
            site_name = named.get('site')
            id = self._cache['vlan'].get(site_name, {}).get(vid, None)
            if id:
                logging.debug(f'using cached id')
                return id
            else:
                vlan = self._get_vlan(vid, site_name)
                if vlan is None:
                    return None
                else:
                    if site_name not in self._cache['vlan']:
                        self._cache['vlan'][site_name] = {}
                    self._cache['vlan'][site_name][vid] = vlan.id
                    return vlan.id
        