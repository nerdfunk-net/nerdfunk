import logging
import requests
import json
from pynautobot import api
from . import git


class Getter(object):

    scope_id_to_name = {'3': 'dcim.device',
                        '4': 'dcim.interface',
                        '11': 'ipam.prefix'}

    def __new__(cls, sot):
        cls._instance = None
        cls._sot = None
        cls._nautobot = None
        cls._output_format = None
        cls._use = None
        cls._cache = {'site':{}, 'vlan': {}, 'tag': {} }

        # singleton
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
        properties = {}
        if len(unnamed) > 0:
            for param in unnamed:
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

    def use(self, use):
        # use another pattern instead of name__ie when query devices
        self._use = use
        return self

    def load_cache(self):
        all_tags = self.query(name='all_tags', 
                                output_format='dict',
                                query_params={})
        vlans_and_sites = self.query(name='all_vlans_and_sites', 
                                output_format='dict',
                                query_params={})

        for tag in all_tags['data']['tags']:
            slug = tag['slug']
            tag_id = tag['id']
            scopes = tag['content_types']
            for scope in scopes:
                scope_id = scope['id']
                # scope_id: 4 interface
                # scope_id: 3 device
                scope_name = self.scope_id_to_name.get(scope_id, scope_id)
                if scope_name not in self._cache['tag']:
                    self._cache['tag'][scope_name] = {}
                self._cache['tag'][scope_name][slug] = tag_id

        for vlan in vlans_and_sites['data']['vlans']:
            site = vlan.get('site')
            if site:
                site_name = site['name']
            else:
                site_name = None
            vlan_vid = vlan['vid']
            vlan_name = vlan['name']
            vlan_id = vlan['id']
            if site_name not in self._cache['vlan']:
                self._cache['vlan'][site_name] = {}
            self._cache['vlan'][site_name][vlan_vid] = vlan_id

        for site in vlans_and_sites['data']['sites']:
            site_name = site.get('name')
            site_id = site.get('id')
            if site_name not in self._cache['site']:
                self._cache['site'][site_name] = {}
            self._cache['site'][site_name] = site_id

    def file(self, *unnamed, **named):
        logging.debug(f'-- entering getter.py/file')
        properties = dict(named)
        if unnamed:
            properties.update(unnamed[0])

        return git.get_file(self._sot.get_config(), properties)

    def device(self, *unnamed, **named):
        logging.debug("-- entering getter.py/device")
        self.open_nautobot()
        getter = None

        if unnamed:
            for item in unnamed:
                if isinstance(item, str):
                    device_name = item
        if 'device' in named:
            getter = {'name__ie': named.get('device')}
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

        device = self._sot.central.get_entity(self._nautobot.dcim.devices, "Device", getter)

        if self._output_format == "obj":
            return device
        elif self._output_format == "dict":
            if device:
                return dict(device)
            else:
                return {}
        elif self._output_format == "json":
            return json.dumps(device)
        else:
            return device

    def devices(self, *unnamed, **named):
        logging.debug("-- entering getter.py/device")

        properties = self.__convert_arguments_to_properties(*unnamed, **named)

        query = {'query_params': properties,
                 'output_format': 'dict'}
        devices = {}
        data = []

        if 'cidr' in properties:
            query['name'] = "device_properties_by_cidr"
        else:
            query['name'] = "device_properties"
        
        logging.debug(f'query: {query}')
        raw = self.query(query)

        if query['name'] == "device_properties_by_cidr":
            for device in raw['data']['ip_addresses']:
                data.append(device.get('primary_ip4_for'))
        if query['name'] == "device_properties":
            data = raw['data']['devices']

        for device in data:
            if device:
                hostname = device.get('hostname')
                devices[hostname] = {'primary_ip': device.get('primary_ip4'),
                                    'device_type': device.get('device_type'),
                                    'device_role': device.get('device_role'),
                                    'platform': device.get('platform')}

        return devices

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

    def query(self, *unnamed, **named):
        logging.debug("-- entering getter.py/query")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)
        query = None
        query_params = None

        if 'name' in properties:
            config = self._sot.get_config()
            query = config['nautobot'].get(properties['name'])
            if query is None:
                logging.error("unkown query %s" % properties['name'])
                return None
        if 'query' in properties:
            query = properties.get('query')
        if 'query_params' in properties:
            query_params = properties['query_params']

        if self._use:
            logging.debug(f'using {self._use} instead of name__ie')
            query = query.replace('name__ie', self._use)
            self._use = None

        self.open_nautobot()
        response = self._nautobot.graphql.query(query=query, variables=query_params).json

        if 'output_format' in properties:
            output_format = properties.get('output_format')
        else:
            output_format = self._output_format

        if output_format == "obj":
            return response
        elif output_format == "dict":
            return dict(response)
        elif output_format == "json":
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
        logging.debug(f'-- entering getter.py/id')
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
                    return site.id
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
        elif item =="tag":
            slug = named.get('slug')
            content_types = named.get('content_types')
            id = self._cache['tag'].get(content_types, {}).get(slug, None)
            if id:
                logging.debug(f'using cached id')
                return id
            try:
                tag = self._nautobot.extras.tags.get(**named)
                if tag:
                    logging.debug(f'adding {content_types} {tag.id} to cache')
                    self._cache['tag'][content_types] = tag.id
                    return tag.id
                else:
                    logging.error(f'unknown tag {slug}')
            except Exception as exc:
                logging.error(f'got exception {exc}')
                return None

    def changes(self, *unnamed, **named):
        logging.debug(f'-- entering getter.py/changes')
        self.open_nautobot()

        properties = self.__convert_arguments_to_properties(unnamed, named)
        if 'start' in properties:
            properties['gt'] = properties.pop('start')
        if 'end' in properties:
            properties['lt'] = properties.pop('end')
        
        changes = self.query(name='changes', query_params=properties)

        if 'context_pattern' in properties:
            data = []
            search = properties.get('context_pattern','')
            for change in changes['data'].get('object_changes'):
                if search in change.get('change_context_detail'):
                    data.append(change)
            return data
        else:
            return changes['data'].get('object_changes')
