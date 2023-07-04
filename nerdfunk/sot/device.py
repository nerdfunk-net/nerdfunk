import logging
import json
import re
import sys
from . import interfaces
from . import ipam
from pynautobot import api
from pynautobot.models.dcim import Devices
from pynautobot.models.dcim import Interfaces as PyInterfaces
from pynautobot.models.ipam import IpAddresses
from .. import devicemanagement as dm
from . import central
from . import git


class Device:
 
    # constant values
    _device_mandatory_properties = ['device_type', 'device_role',
                                    'platform', 'site', 'status']
    _device_default_values = {'device_type': {'slug': 'default-type'},
                              'device_role': {'slug': 'default-role'},
                              'platform': {'slug': 'ios'},
                              'site': {'name': 'default-site'},
                              'status': 'active'}
    # regex
    _REGEX_IPV4 = r"^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$"

    def __init__(self, sot, device_or_ip):
        logging.debug("-- entering sot/device.py/__init__")
        logging.debug(f'initializing device {device_or_ip} (device.py)')

        # init variables
        self._last_attribute = None
        self._todos = {}
        self._use_defaults = False
        self._return_device = True

        # device properties
        self._device_name = None
        self._device_obj = None
        self._device_ip = None
        self._device_properties = {}

        # dict of all interfaces of the device
        self._interfaces = {}
        self._interface_defaults = {}

        # tags
        self._device_tags = []

        self._primary_ipv4 = None
        self._primary_interface = None
        self._primary_interface_properties = None
        self._make_interface_primary = None
        self._last_request = None
        self._last_requested_interface = None
        self._last_requested_tags = None

        # connection to nautobot
        self._nautobot = None
        self._sot = sot
        # check if device_or_ip is IP or name:
        if re.match(self._REGEX_IPV4, device_or_ip):
            logging.debug(f'{device_or_ip} is an IP address')
            self._device_ip = device_or_ip
        else:
            self._device_name = device_or_ip

    # -----===== internals =====-----

    def open_nautobot(self):
        if self._nautobot is None:
            self._nautobot = api(self._sot.get_nautobot_url(), token=self._sot.get_token())

    def _get_device_from_nautobot(self, refresh=False):
        logging.debug("-- entering sot/device.py/_get_device_from_nautobot")
        # sometimes we need to refresh the object eg. when adding tags
        # when adding a a list of tags the object will not notice that the tags
        # have changed
        if self._device_obj is None or refresh:
            logging.debug("getting device from sot")
            self.open_nautobot()
            if self._device_name is not None:
                self._device_obj = self._sot.central.get_entity(self._nautobot.dcim.devices,
                                                                "Device",
                                                                {'name': self._device_name})
            elif self._device_ip is not None:
                logging.debug(f'sending query to get device using IP {self._device_ip}')
                self._device_obj = self._sot.get.device(ip=self._device_ip)

        return self._device_obj

    def _get_interface(self, interface):
        if interface not in self._interfaces:
            if self._device_obj is None:
                self._device_obj = self._get_device_from_nautobot()
            self._interfaces[interface] = interfaces.Interface(
                interface,
                self._sot,
                self._get_device_from_nautobot())
            self._last_request = None
            self._last_requested_interface = None
        return self._interfaces[interface].get()

    def _get_token(self):
        return self._sot.get_token()

    def _get_nautobot_url(self):
        return self._sot.get_nautobot_url()

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
                elif isinstance(param, tuple):
                    for tup in param:
                        if isinstance(tup, dict):
                            for key,value in tup.items():
                                properties[key] = value
                elif isinstance(param, list):
                    return param
                else:
                    logging.error(f'cannot use paramater {param} / {type(param)} as value')
        for key,value in named.items():
                properties[key] = value
        
        return properties

    # -----===== user commands =====-----

    def get(self):
        logging.debug("-- entering sot/device.py/get")
        logging.debug(f'returning obj of device {self._device_name}')
        return self._get_device_from_nautobot()

    def get_all_interfaces(self):
        logging.debug("-- entering sot/device.py/get_all_interfaces")
        self.open_nautobot()
        return self._nautobot.dcim.interfaces.filter(device_id=self._get_device_from_nautobot().id)

    def add(self, *unnamed, **named):
        logging.debug("-- entering sot/device.py/add")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)
        return self.add_device(properties)

    def update(self, *unnamed, **named):
        logging.debug("-- entering sot/device.py/update")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)
        if 'name' not in properties:
                properties['name'] = self._device_name
        return self.update_device(properties)

    def delete(self):
        logging.debug("-- entering sot/device.py/delete")
        return self.delete_device()

    def set_tags(self, tags):
        # set tags overwrites existing tags
        return self.modify_tags(tags, set_tag=True, remove_tags=False)

    def add_tags(self, tags):
        # add tag to existing ones
        return self.modify_tags(tags, set_tag=False, remove_tags=False)

    def delete_tags(self, tags):
        # remove tags
        return self.modify_tags(tags, set_tag=False, remove_tags=True)

    def modify_tags(self, new_tags, set_tag=False, remove_tags=False):
        logging.debug("-- entering sot/device.py/add_tags")
        logging.debug(f'adding tags {new_tags} on device {self._device_name}')
        tags = set()
        if isinstance(new_tags, str):
            tags.add(new_tags)
        elif isinstance(new_tags, list):
            for tag in new_tags:
                tags.add(tag)
        else:
            logging.error(f'please add tags as string or list of strings')
            return None
        if set_tag:
            return self.set_device_tags(tags)
        elif remove_tags:
            return self.delete_device_tags(tags)
        else:
            return self.add_device_tags(tags)    

    def set_config_context(self, config_context):
        logging.debug("-- entering sot/device.py/set_config_context")
        logging.debug(f'writing config context of {self._device_name}')
        return git.edit_file(self._sot.get_config(), config_context)

    def connection_to(self, *unnamed, **named):
        logging.debug("-- entering sot/device.py/connection_to")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)
        self.open_nautobot()
        
        name_of_side_b = properties.get('device')
        name_of_interface_b = properties.get('interface')

        logging.debug(
            f'connect device {self._device_name}/{self._last_requested_interface} to {name_of_side_b}/{name_of_interface_b}')

        interface_a = self._get_interface(self._last_requested_interface)
        side_b = self._sot.central.get_entity(self._nautobot.dcim.devices,
                                              "Device",
                                              {'name': name_of_side_b})
        interface_b = self._sot.central.get_entity(self._nautobot.dcim.interfaces,
                                              "Interface",
                                              {'device_id': side_b.id,
                                               'name': name_of_interface_b})
        
        if side_b is not None and interface_b is not None:
            self._last_requested_interface = None
            cable = {
                'termination_a_type': 'dcim.interface',
                'termination_a_id': interface_a.id,
                'termination_b_type': 'dcim.interface',
                'termination_b_id': interface_b.id,
                'type': 'cat5e',
                'status': 'connected'
            }
            success = self._sot.central.add_entity(self._nautobot.dcim.cables, cable)

            if success:
                logging.debug(f'connection created successfully')
            else:
                logging.error(f'connection could not created successfully')

    def add_list_of_interfaces(self, list_of_interfaces):
        logging.debug('-- entering device.py/add_list_of_interfaces')
        self.open_nautobot()

        try:
            nb_interface = self._nautobot.dcim.interfaces.create(list_of_interfaces)
        except Exception as exc:
            logging.error(f'could not add interfaces; got exception {exc}')
            return None

    # -----===== attributes =====-----

    def use_defaults(self, use_defaults):
        logging.debug('-- entering device.py/use_defaults')
        logging.debug(f'setting use_defaults to {use_defaults} (device)')
        self._use_defaults = use_defaults
        return self

    def primary_ipv4(self, primary_ipv4):
        logging.debug('-- entering device.py/primary_ipv4')
        if isinstance(primary_ipv4, IpAddresses) or isinstance(primary_ipv4, str):
            logging.debug(f'setting primary_ipv4 to {primary_ipv4}')
            self._primary_ipv4 = primary_ipv4
        else:
            logging.error("wrong instance; please use Interface or str")
            self._primary_ipv4 = None
            return self
        return self

    def primary_interface(self, *unnamed, **named):
        logging.debug("-- entering sot/device.py/primary_interface")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)

        if isinstance(properties, dict):
            logging.debug(f'setting primary_interface_properties to {properties}')
            self._primary_interface_properties = properties
            self._primary_interface = properties.get('name', None)
        else:
            logging.debug(f'setting _primary_interface to {properties}')
            self._primary_interface = properties
        return self

    def make_primary(self, make_primary):
        logging.debug('-- entering device.py/make_primary')
        logging.debug(f'making interface the primary interface')
        self._make_interface_primary = True
        return self

    def interface(self, interface_name):
        logging.debug('-- entering device.py/interface')
        logging.debug(f'setting _last_requested_interface to {interface_name}')
        return interfaces.Interface(
                    interface_name,
                    self._sot,
                    self._get_device_from_nautobot())

    def return_device(self, return_device):
        logging.debug('-- entering device.py/return_device')
        # return_device == True: return device instead of None if device
        # is already part of sot
        logging.debug(f'setting _return_device to {return_device}')
        self._return_device = return_device
        return self

    # -----===== Device Management =====-----

    def add_device(self, device_properties):
        logging.debug('-- entering device.py/add_device')
        self.open_nautobot()
        logging.debug(f'add device: {device_properties} use_defaults: {self._use_defaults}')
        for key in self._device_mandatory_properties:
            if key not in device_properties:
                if self._use_defaults:
                    logging.error(f'mandatory property {key} is missing; using default')
                    device_properties[key] = self._device_default_values.get(key)
                else:
                    logging.error(f'mandatory property {key} is missing')
                    logging.debug(f'-- leaving device.py/add_device')
                    return False

        device_properties['name'] = self._device_name
        nb_device = self._sot.central.add_entity(self._nautobot.dcim.devices, device_properties)
        if nb_device is None:
            logging.error(f'could not add device {self._device_name} to SOT')
            self._sot.log(device=self._device_name, log='could not add device to SOT')
            logging.debug(f'-- leaving device.py/add_device')
            return None

        self._sot.log(device=self._device_name, log='device added to SOT')
        # check if we have to add a primary interface
        if self._primary_interface:
            logging.debug("adding primary interface %s" % self._primary_interface)
            interface = interfaces.Interface(self._primary_interface, self._sot, self._get_device_from_nautobot())
            primary_interface = interface \
                .set_device(nb_device) \
                .use_defaults(True) \
                .add(self._primary_interface_properties)

            if primary_interface is None:
                logging.error("creating interface failed")
                self._sot.log(device=self._device_name, log='could not create primary interface')
                logging.debug(f'-- leaving device.py/add_device')
                return nb_device

            if self._primary_ipv4 is None:
                logging.debug("no primary ipv4 specified; skipping assignment of the interface")
                logging.debug(f'-- leaving device.py/add_device')
                return nb_device
            else:
                logging.debug(f'using primary IP {self._primary_ipv4}')

            # add primary IP address to sot
            primary_ipv4 = self._sot.ipam \
                .ipv4(self._primary_ipv4) \
                .add({'status': 'active'})

            if primary_ipv4:
                logging.debug(f'added ip address to sot; now assign interface {primary_interface} to {self._primary_ipv4}')
                assigned_interface = self._sot.ipam \
                    .assign(primary_interface) \
                    .on(nb_device) \
                    .to(self._primary_ipv4)
            else:
                logging.error("could not add ip address (%s); assigning interface to ipv4 not possible" %
                              self._primary_ipv4)

            # make interface primary
            if self._make_interface_primary:
                logging.debug("mark interface as primary")
                try:
                    success = nb_device.update({'primary_ip4': primary_ipv4.id})
                except Exception as exc:
                    logging.error(f'updating {self._device_name} failed; got exception %s' % exc)
                    return None
                if success is None:
                    logging.error("make interface primary failed")
                    logging.debug(f'-- leaving device.py/add_device')
                    return None
                else:
                    self._sot.log(device=self._device_name, 
                                  log=f'added {self._primary_ipv4} to SOT and make {primary_interface} primary')
                    logging.debug('successfully marked interface as primary')
    
        logging.debug(f'-- leaving device.py/add_device')
        return nb_device

    def update_device(self, device_properties, convert_to_id=True):
        logging.debug('-- entering device.py/update_device')
        self.open_nautobot()

        nb_device = self._get_device_from_nautobot()
        if nb_device is None:
            logging.info("device %s does not exists" % self._device_name)
            return None

        if convert_to_id:
            logging.debug("converting properties to IDs")
            success, error = self._sot.central.get_ids(device_properties)
            if not success:
                logging.error(f'could not convert properties to IDs; {error}')
                return None
        try:
            success = nb_device.update(device_properties)
            logging.debug('device %s updated successfully' % device_properties['name'])
            return nb_device
        except Exception as exc:
            logging.error(f'could not update device; got exception %s' % exc)
            return None

    def delete_device(self):
        logging.debug('-- entering device.py/delete_device')
        self.open_nautobot()
        logging.debug(f'deleting device {self._device_name} from sot')

        return self._sot.central.delete_entity(self._nautobot.dcim.devices, "Device", {'name': self._device_name}, {'name': self._device_name})

    def set_customfield(self, *unnamed, **named):
        logging.debug('-- entering device.py/set_customfield')
        properties = self.__convert_arguments_to_properties(*unnamed, **named)
        self.open_nautobot()

        if self._last_request == "interface":
            logging.debug(f'setting custom field {properties} on interface {self._last_requested_interface}')
            if self._last_requested_interface is not None and self._last_requested_interface not in self._interfaces:
                logging.debug(f'adding interface {self._last_requested_interface} to list of interfaces')
                self._interfaces[self._last_requested_interface] = interfaces.Interface(
                    self._last_requested_interface,
                    self._sot,
                    self._get_device_from_nautobot())

            return self._interfaces[self._last_requested_interface].set_customfield(properties)
        else:
            logging.debug(f'setting custom field {properties} on device {self._device_name}')
            return self._sot.central.update_entity(self._nautobot.dcim.devices,
                                                   {'custom_fields': properties},
                                                   {'name': self._device_name})

    def set_device_tags(self, new_tags):
        self.add_device_tags(new_tags, True)

    def add_device_tags(self, new_tags, set_tag=False):
        logging.debug('-- entering device.py/add_device_tags')
        self.open_nautobot()
        final_list = []

        if not set_tag:
            # if the device already exists there may also be tags
            device = self._get_device_from_nautobot(refresh=True)
            if device is None:
                logging.error(f'unknown device {self._device_name}')
                return None

            for tag in device.tags:
                new_tags.add(tag.name)

            logging.debug(f'current tags: {device.tags}')
            logging.debug(f'updating tags to {new_tags}')

        # check if new tag is known; add id to final list
        for new_tag in new_tags:
            tag = self._sot.central.get_entity(self._nautobot.extras.tags, "Tag", {'name': new_tag})
            if tag is None:
                logging.error(f'unknown tag {new_tag}')
            else:
                final_list.append(tag.id)

        if len(final_list) > 0:
            properties = {'tags': list(final_list)}
            logging.debug(f'final list of tags {properties}')
            return self._sot.central.update_entity(self._nautobot.dcim.devices,
                                                   properties,
                                                   {'name': self._device_name})

    def delete_device_tags(self):
        logging.debug('-- entering device.py/delete_tags')
        self.open_nautobot()
        logging.debug(f'deleting tags {self._tags_to_delete} from sot')

        new_device_tags = self._tags_to_delete

        # the device must exist; get tags
        device = self._get_device_from_nautobot()
        if device is None:
            logging.error(f'unknown device {self._device_name}')
            return None

        for tag in device.tags:
            if tag in new_device_tags:
                new_device_tags.remove(tag)

        logging.debug(f'current tags: {device.tags}')
        logging.debug(f'new tags {new_device_tags}')

        properties = {'tags': list(new_device_tags)}
        # todo hier noch einmal schauen und testen
        return self._sot.central.update_entity(self._nautobot.extras.tags,
                                               properties,
                                               {'name': self._device_name})
