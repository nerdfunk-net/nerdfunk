import logging
import os
import json
from ..utilities import misc
from collections import defaultdict
from ttp import ttp


class Configparser(object):

    def __init__(self, sot, *unnamed, **named):
        logging.debug(f'Creating CONFIGPARSER object')
        properties = self.__convert_arguments_to_properties(unnamed, named)
        self._sot = sot
        self._device_config = properties.get('config', None)
        self._output_format = properties.get('output_format', 'json')
        self._parser = None
        self._template = None
        self._template_filename = None
        self._sot_config = sot.get_config()
        # naming is used to save the exact spelling of the interface
        # nxos and ios differs using Port-channel/Port-Channel/port-channel
        self._naming = {}
        self._my_config = misc.read_config("%s/%s" % (
                os.path.abspath(os.path.dirname(__file__)),
                self._sot_config['configparser'].get('config') ))
        self.parse(*unnamed, **named)

    def __convert_arguments_to_properties(self, *unnamed, **named):
        """ converts unnamed (dict) and named arguments to a single property dict """
        properties = {}
        for param in unnamed:
            if len(param) == 0:
                continue
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

    def _get_template(self, properties):
        basedir = os.path.abspath(os.path.dirname(__file__))

        if self._template is not None:
            return self._template
        if 'template' in properties:
            return properties.get('template')

        if self._template_filename is None:
            platform = properties.get('platform','ios')
            # use default template that is configured in config
            filename = self._my_config.get('templates',{}).get(platform, None)
            logging.debug(f'using ttp template {filename}')
        else:
            filename = self._template_filename
        if filename is None:
            logging.error(f'please configure correct template filename for {platform}')
            return None
        try:
             with open("%s/%s" % (basedir, filename)) as f:
                ttp_template = f.read()
        except:
            logging.error(f'could not read template')
            return None
        
        return ttp_template

    def _save_naming(self):
        for interface in self._parsed_config[0].get('interfaces', {}):
            if 'Port-channel' in interface:
                self._naming["port-channel"] = "Port-channel"
            if 'port-channel' in interface:
                self._naming["port-channel"] = "port-channel"

    def format(self, format):
        self._output_format = format
        return self

    def template(self, *unnamed, **named):
        properties = self.__convert_arguments_to_properties(unnamed, named)
        if 'file' in properties:
            self._template_filename = properties.get('file')
        if 'template' in properties:
            self._template = properties.get('template')
        return self

    def parse(self, *unnamed, **named):
        logging.debug(f'-- entering configparser.py/parse')
        properties = self.__convert_arguments_to_properties(unnamed, named)

        # get template
        ttp_template = self._get_template(properties)
    
        if self._device_config:
            device_config = self._device_config
        if 'config' in properties:
            device_config = properties.get('config')

        # create parser object and parse data using template:
        self._parser = ttp(data=device_config, template=ttp_template)
        self._parser.parse()
        self._parsed_config = self._parser.result(format='raw')[0]
        self._save_naming()

    def get(self, *unnamed, **named):
        logging.debug(f'-- entering configparser.py/get')
        properties = self.__convert_arguments_to_properties(unnamed, named)

        format = properties.get('output_format', self._output_format)
        return self._parser.result(format=format)[0]

    def get_interface_name_by_address(self, address):
        logging.debug(f'-- entering configparser.py/get_interface_name_by_address')
        interfaces = self._parsed_config[0].get('interfaces', {})
        ip = address.split('/')[0]
        for name, properties in interfaces.items():
            if ip == properties.get('ip'):
                logging.debug(f'found IP {ip} on {name}')
                return name
        return None
    
    def get_interface(self, interface):
        logging.debug(f'-- entering configparser.py/get_interface')
        return self._parsed_config[0].get('interfaces', {}).get(interface, None)

    def get_interfaces(self):
        logging.debug(f'-- entering configparser.py/get_interface')
        return self._parsed_config[0].get('interfaces', None)

    def get_ipaddress(self, interface):
        logging.debug(f'-- entering configparser.py/get_ipaddress')
        return self._parsed_config[0].get('interfaces', {}).get(interface, {}).get('ip', None)

    def get_vlans(self):
        logging.debug(f'-- entering configparser.py/get_vlans')
        global_vlans = []
        svi = []
        trunk_vlans = []

        for vid, properties in self._parsed_config[0].get('global',{}).get('vlan',{}).items():
            global_vlans.append({'vid': vid,
                                 'name': properties.get('name', 'unknown')})
    
        for name, properties in self._parsed_config[0].get('interfaces', {}).items():
            if 'vlan' in name.lower():
                svi.append({'vid': name[4:],
                            'name': properties.get('description','unkown')})
            if 'vlans_allowed' in properties:
                for vid in properties.get('vlans_allowed'):
                    trunk_vlans.append({'vid': vid,
                                        'name': 'trunked VLAN'})

        return global_vlans, svi, trunk_vlans
    
    def get_name(self, name):
        return self._naming.get(name.lower(), name)

    def get_device_config(self):
        return self._device_config

    def get_section(self, section):
        logging.debug(f'-- entering configparser.py/get_section')
        response = []
        if section == "interfaces":
            found = False
            for line in self._device_config.splitlines():
                # find first occurence of the word interface at the beginning of the line
                if line.lower().startswith('interface '):
                    found = True
                    response.append(line)
                    continue
                if found and line.startswith(' '):
                    response.append(line)
                else:
                    found = False
        return response
