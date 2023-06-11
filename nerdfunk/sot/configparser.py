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

    def get_global_config(self):
        logging.debug(f'-- entering configparser.py/get_global')

        response = []
        for line in self._device_config.splitlines():
            if line.lower().startswith('interface '):
                found = True
                continue
            elif not line.lower().startswith('interface '):
                found = False
            if not found:
                response.append(line)

        return response

    def _find_in_line(self, key, lookup, value, line):
        """
        n - not equal to (negation)
        ic - case-insensitive contains (*)
        c - case-sensitive contains (*)
        ie - case-insensitive exact match (*)

        nic - negated case-insensitive contains
        isw - case-insensitive starts-with
        nisw - negated case-insensitive starts-with
        iew - case-insensitive ends-with
        niew - negated case-insensitive ends-with
        nie - negated case-insensitive exact match
        re - case-sensitive regular expression match
        nre - negated case-sensitive regular expression match
        ire - case-insensitive regular expression match
        nire - negated case-insensitive regular expression match
        """

        # logging.debug(f'key: {key} lookup: {lookup} value: {value} line: {line}')
        if key == 'match':
            if lookup == "ie":
                # case-insensitive exact match
                if line.lower() == value.lower():
                    return True
            elif lookup == "ic":
                # case-insensitive contains
                if value.lower() in line.lower():
                    return True
            elif lookup == "c":
            # case-sensitive contains
                if value in line:
                    return True
            else:
                if line == value:
                    return True

        return False

    def find_in_global(self, properties):
        logging.debug(f'-- entering configparser.py/find_in_global')

        key = None
        value = None
        ignore_leading_spaces = False

        for k,v in properties.items():
            if 'match' in k:
                key = k
                value = v
            elif 'ignore_leading_spaces' == k:
                ignore_leading_spaces = v
    
        global_config = self.get_global_config()

        # the key can be match__ic etc.
        cmd = key.split('__')[0]
        if '__' in key:
            lookup = key.split('__')[1]

        logging.debug(f'cmd: "{cmd}" lookup: "{lookup}" value: "{value}" lines: {len(global_config)}')

        for line in global_config:
            if properties.get('ignore_leading_spaces'):
                src = line.lstrip()
            else:
                src = line

            if self._find_in_line(cmd, lookup, value, src):
                logging.debug(f'found pattern in global config')
                return True
        
        return False

    def find_in_interfaces(self, properties):
        logging.debug(f'-- entering configparser.py/find_in_interfaces')

        key = None
        value = None
        ignore_leading_spaces = False

        for k,v in properties.items():
            if 'match' in k:
                key = k
                value = v
            elif 'ignore_leading_spaces' == k:
                ignore_leading_spaces = v
    
        interface_config = self.get_section('interfaces')

        # matched_on contains the list of all interfaces the value matched
        matched_on = []
        # the key can be match__ic etc.
        cmd = key.split('__')[0]
        if '__' in key:
            lookup = key.split('__')[1]

        logging.debug(f'cmd: "{cmd}" lookup: "{lookup}" value: "{value}" lines: {len(interface_config)}')

        for line in interface_config:
            if ignore_leading_spaces:
                src = line.lstrip()
            else:
                src = line

            if src.lower().startswith('interface '):
                interface = line[10:]
            
            if self._find_in_line(cmd, lookup, value, src):
                matched_on.append(interface)

        logging.debug(f'matched_on={matched_on}')
        return matched_on