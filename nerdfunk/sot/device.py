import logging
import json
from . import interfaces
from . import ipam
from pynautobot import api
from pynautobot.models.dcim import Devices
from pynautobot.models.dcim import Interfaces as PyInterfaces
from pynautobot.models.ipam import IpAddresses
from . import central
from . import git


class Device(object):
    _last_attribute = None
    _sot = None
    _todos = {}
    _use_defaults = False
    _return_device = True

    # device properties
    _device_name = None
    _device_obj = None
    _device_properties = {}
    _device_mandatory_properties = ['device_type', 'device_role',
                                    'platform', 'serial', 'site', 'status']
    _device_default_values = {'device_type': 'default_type',
                              'device_role': 'default_role',
                              'platform': 'ios',
                              'site': 'default_site',
                              'status': 'active'}

    # dict of all interfaces of the device
    _interfaces = {}
    _interface_defaults = {}

    # tags
    _device_tags = []

    _primary_ipv4 = None
    _primary_interface = None
    _primary_interface_properties = None
    _make_interface_primary = None
    _last_request = None
    _last_requested_interface = None
    _last_requested_tags = None

    # connection to nautobot
    _nautobot = None

    def __init__(self, sot, devicename):
        logging.debug("-- entering sot/device.py.py/__init__")
        logging.debug(f'initializing device {devicename} (device.py)')
        self._sot = sot
        self._device_name = devicename

    # internal method 

    def open_nautobot(self):
        if self._nautobot is None:
            self._nautobot = api(self._sot.get_nautobot_url(), token=self._sot.get_token())

    def _get_device_from_nautobot(self):
        logging.debug("-- entering sot/device.py.py/_get_device_from_nautobot")
        if self._device_obj is None:
            logging.debug("getting device from sot")
            self.open_nautobot()
            self._device_obj = self._sot.central.get_entity(self._nautobot.dcim.devices, 
                                                  "Device", 
                                                  {'name': self._device_name},
                                                  {'name': self._device_name})
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

    def set_interface_defaults(self, defaults):
        logging.debug("-- entering sot/device.py.py/set_interface_defaults")
        logging.debug(f'setting interface defaults to {defaults}')
        self._interface_defaults = defaults
        return self

    def get(self):
        logging.debug("-- entering sot/device.py.py/get")
        if self._last_request == "interface":
            interface = self._last_requested_interface
            if interface is None:
                logging.error(f'no interface specified and get called')
                return None
            return self._get_interface(interface)
        else:
            logging.debug(f'returning obj of device {self._device_name}')
            return self._get_device_from_nautobot()

    def add(self, *unnamed, **named):
        logging.debug("-- entering sot/device.py.py/add")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)

        if self._last_request == "interface":
            interface = self._last_requested_interface
            self._last_requested_interface = None
            self._last_request = None
            if interface is not None and interface not in self._interfaces:
                self._interfaces[interface] = interfaces.Interface(
                    interface,
                    self._sot,
                    self._get_device_from_nautobot())
            return self._interfaces[interface] \
                .use_defaults(self._use_defaults) \
                .add(properties)
        else:
            return self.add_device(properties)

    def add_range(self, first_interface, last_interface):
        logging.debug("-- entering sot/device.py.py/add_range")
        logging.debug(f'adding interface {first_interface} to {last_interface}')

        prefix = first_interface[:first_interface.rfind('/')]
        start = int(first_interface.split('/')[-1])
        for i in range(start, last_interface + 1):
            interface = "%s/%s" % (prefix, i)
            if interface is not None and interface not in self._interfaces:
                self._interfaces[interface] = interfaces.Interface(
                    interface,
                    self._sot,
                    self._get_device_from_nautobot())
                self._interfaces[interface] \
                    .use_defaults(self._use_defaults) \
                    .add(self._interface_defaults)

    def update(self, *unnamed, **named):
        logging.debug("-- entering sot/device.py.py/update")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)
        if self._last_request == "interface":
            interface = self._last_requested_interface
            self._last_requested_interface = None
            self._last_request = None
            if interface is not None and interface not in self._interfaces:
                self._interfaces[interface] = interfaces.Interface(
                    interface,
                    self._sot,
                    self._get_device_from_nautobot())
            return self._interfaces[interface] \
                .use_defaults(self._use_defaults) \
                .update(properties)
        else:
            logging.debug(f'update device: {properties}')
            if 'name' not in properties:
                properties['name'] = self._device_name
            return self.update_device(properties)

    def delete(self):
        logging.debug("-- entering sot/device.py.py/delete")
        if self._last_request == "interface":
            interface = self._last_requested_interface
            self._last_requested_interface = None
            self._last_request = None
            # todo
        elif self._last_request == "tags":
            self._last_request = None
            for tag in self._last_requested_tags:
                self._tags_to_delete.add(tag)
            return self.delete_tags()
        else:
            return self.delete_device()

    def add_tags(self, new_tags):
        logging.debug("-- entering sot/device.py.py/add_tags")
        if self._last_request == "interface":
            logging.debug(f'setting tags {new_tags} on interface {self._last_requested_interface}')
            if self._last_requested_interface is not None and self._last_requested_interface not in self._interfaces:
                logging.debug(f'adding interface {self._last_requested_interface} to list of interfaces')
                self._interfaces[self._last_requested_interface] = interfaces.Interface(
                    self._last_requested_interface,
                    self._sot,
                    self._get_device_from_nautobot())
            tags = set()
            if isinstance(new_tags, str):
                tags.add(new_tags)
            elif isinstance(new_tags, list):
                for tag in new_tags:
                    tags.add(tag)
            return self._interfaces[self._last_requested_interface].add_tags(tags)
        else:
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
            return self.add_device_tags(tags)

    def add_or_update(self, update_configured):
        logging.debug("-- entering sot/device.py.py/add_or_update")
        self.open_nautobot()
        add_device = True
        update_device = False
        if self._get_device_from_nautobot():
            add_device = False
            logging.info(f'device {self._device_name} found in SOT!')
            if update_configured:
                logging.info(f'updating is set to true; updating device')
                update_device = True
            else:
                logging.info(f'skipping functionality')
        return add_device, update_device

    def set_config_context(self, config_context):
        logging.debug("-- entering sot/device.py.py/set_config_context")
        logging.debug(f'writing config context of {self._device_name}')
        return git.edit_file(self._sot.get_config(), config_context)

    def write_backup(self, config_context):
        logging.debug("-- entering sot/device.py.py/write_backup")
        logging.debug(f'writing config backup {self._device_name}')
        return git.edit_file(self._sot.get_config(), config_context)

    def connection_to(self, *unnamed, **named):
        logging.debug("-- entering sot/device.py.py/connection_to")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)
        self.open_nautobot()
        
        name_of_side_b = properties.get('device')
        name_of_interface_b = properties.get('interface')

        logging.debug(
            f'connect device {self._device_name}/{self._last_requested_interface} to {name_of_side_b}/{name_of_interface_b}')

        interface_a = self._get_interface(self._last_requested_interface)
        side_b = self._sot.central.get_entity(self._nautobot.dcim.devices,
                                              "Device",
                                              {'name': name_of_side_b},
                                              {'name': name_of_side_b})
        interface_b = self._sot.central.get_entity(self._nautobot.dcim.interfaces,
                                              "Interface",
                                              {'device_id': side_b.id,
                                               'name': name_of_interface_b},
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
            success = self._sot.central.add_entity(self._nautobot.dcim.cables,
                                                   cable,
                                                   "Cable",
                                                   cable,
                                                   None,
                                                   False)

            if success:
                logging.debug(f'connection created successfully')
            else:
                logging.error(f'connection could not created successfully')

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
        logging.debug("-- entering sot/device.py.py/primary_interface")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)

        logging.debug(f'setting primary_interface_properties to {properties}')
        self._primary_interface_properties = properties
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
        self._last_request = "interface"
        self._last_requested_interface = interface_name
        return self

    def tag(self, tag):
        logging.debug('-- entering device.py/tag')
        logging.debug(f'adding {tag} to list of_last_requested_tags')
        self._last_request = "tags"
        if self._last_requested_tags is None:
            self._last_requested_tags = set()
        self._last_requested_tags.add(tag)
        return self

    def tags(self, tags):
        logging.debug('-- entering device.py/tags')
        logging.debug(f'setting _last_requested_tags to {tags}')
        self._last_request = "tags"
        if self._last_requested_tags is None:
            self._last_requested_tags = set()
        for tag in tags:
            self._last_requested_tags.add(tag)
        return self

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
        nb_device = self._sot.central.add_entity(self._nautobot.dcim.devices, 
                                    device_properties, 
                                    "Device", 
                                    {'name': self._device_name},
                                    {'name': self._device_name},
                                    self._return_device)
        if nb_device is None:
            logging.error(f'could not add device {self._device_name} to SOT')
            logging.debug(f'-- leaving device.py/add_device')
            return None

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
                success = nb_device.update({'primary_ip4': primary_ipv4.id})
                if success is None:
                    logging.error("make interface primary failed")
                    logging.debug(f'-- leaving device.py/add_device')
                    return None
                else:
                    logging.debug('successfully marked interface as primary')
    
        logging.debug(f'-- leaving device.py/add_device')
        return nb_device

    def update_device(self, device_properties):
        logging.debug('-- entering device.py/update_device')
        self.open_nautobot()

        nb_device = self._get_device_from_nautobot()
        if nb_device is None:
            logging.info("device %s does not exists" % self._device_name)
            return None

        logging.debug("converting properties to IDs")
        logging.debug(device_properties)
        success, error = self._sot.central.get_ids(device_properties)
        if not success:
            logging.error(f'could not convert properties to IDs; {error}')
            return None

        try:
            success = nb_device.update(device_properties)
            logging.debug('device %s updated successfully' % device_properties['name'])
            return nb_device
        except Exception as exc:
            logging.error(f'could not add device to nautobot; got exception %s' % exc)
            return None

    def delete_device(self):
        logging.debug('-- entering device.py/delete_device')
        self.open_nautobot()
        logging.debug(f'deleting device {self._device_name} from sot')

        return self._sot.central.delete_entity(self._nautobot.dcim.devices, "Device", {'name': self._device_name}, {'name': self._device_name})

    def add_device_tags(self, new_tags):
        logging.debug('-- entering device.py/add_device_tags')
        self.open_nautobot()

        # if the device already exists there may also be tags
        device = self._get_device_from_nautobot()
        if device is None:
            logging.error(f'unknown device {self._device_name}')
            return None

        for tag in device.tags:
            new_tags.add(tag.name)

        logging.debug(f'current tags: {device.tags}')
        logging.debug(f'updating tags to {new_tags}')

        # check if tags are known
        for new_tag in new_tags:
            tag = self._sot.central.get_entity(self._nautobot.extras.tags,
                                     "Tag",
                                     {'name': new_tag},
                                     {'name': new_tag},
                                     self._last_request)
            if tag is None:
                logging.error(f'unknown tag {tag}')
                new_tags.remove(tag)

        properties = {'tags': list(new_tags)}
        logging.debug(f'final list of tags {properties}')
        return self._sot.central.update_entity(self._nautobot.dcim.devices,
                                     properties,
                                     'Tags',
                                     properties,
                                     {'name': self._device_name})

    def delete_tags(self):
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
        return self._sot.central.update_entity(self._nautobot.extras.tags,
                                     properties,
                                     'Tags',
                                     properties,
                                     {'name': self._device_name},
                                     self._nautobot.dcim.devices)
