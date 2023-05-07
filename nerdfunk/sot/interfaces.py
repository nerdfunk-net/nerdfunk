import logging
import json
from pynautobot import api
from pynautobot.models.dcim import Devices
from pynautobot.models.dcim import Interfaces


class Interface(object):
    _sot = None
    _last_attribute = None
    _device = None
    _todos = {}
    _use_defaults = False
    _return_interface = True
    _bulk = False

    # interface properties
    _interface_name = None
    _interface_obj = None
    _interface_properties = {}
    _interface_mandatory_properties = ['name', 'description', 'status', 'type']
    _interface_default_values = {'description':'',
                                 'status': 'active',
                                 'type': '1000base-t'}

    # connection to nautobot
    _nautobot = None

    # tags
    _interface_tags = []
    _tags_to_delete = set()
    _tags_to_add = set()

    def __init__(self, interface_name, sot, device=None):
        logging.debug("-- entering sot/interfaces.py.py/__init__")
        logging.debug(f'initializing interface {interface_name} on {device}')
        self._interface_name = interface_name
        self._sot = sot
        self._device = device

    # internal method 

    def open_nautobot(self):
        if self._nautobot is None:
            self._nautobot = api(self._sot.get_nautobot_url(), token=self._sot.get_token())

    def _get_interface_from_nautobot(self):
        if self._interface_obj is None:
            self.open_nautobot()
            logging.debug(f'getting interface {self._interface_name} from device {self._device.name}')
            self._interface_obj = self._nautobot.dcim.interfaces.get(
                device_id=self._device.id,
                name=self._interface_name)
        return self._interface_obj

    def __convert_arguments_to_properties(self, *unnamed, **named):
        """ converts unnamed (dict) and named arguments to a single property dict """
        logging.debug("-- entering interfaces.py/__convert_arguments_to_properties")
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
        logging.debug("-- leaving interfaces.py/__convert_arguments_to_properties")
        return properties

    # -----===== user commands =====----- 

    def get(self):
        logging.debug("-- entering sot/interfaces.py.py/get")
        if self._interface_obj is None:
            return self._get_interface_from_nautobot()
        return self._interface_obj

    def get_properties(self, *unnamed, **named):
        logging.debug("-- entering sot/interfaces.py.py/_get_properties")
        logging.debug(f'unnamed: {unnamed} named: {named}')
        properties = self.__convert_arguments_to_properties(*unnamed, **named)
        if 'name' not in properties:
            properties['name'] = self._interface_name
        logging.debug(f'add interface: {self._interface_name} use_defaults: {self._use_defaults}')

        for key in self._interface_mandatory_properties:
            if key not in properties:
                if self._use_defaults:
                    logging.error(f'mandatory property {key} is missing; using default')
                    properties[key] = self._interface_default_values.get(key)
                else:
                    logging.error(f'mandatory property {key} is missing')
                    return None

        # convert property values to id (vlan, tags, etc.)
        success, error = self._sot.central.get_ids(properties)
        if not success:
            logging.error(f'could not convert properties to IDs; {error}')
            return None
        # add device name to properties if not set by user
        if 'device' not in properties:
            properties['device'] = self._device.id

        return properties

    def add(self, *unnamed, **named):
        logging.debug("-- entering sot/interfaces.py.py/add")
        logging.debug(f'unnamed: {unnamed} named: {named}')
        return self.__add_interface(self.get_properties(*unnamed, **named))

    def update(self, *unnamed, **named):
        logging.debug("-- entering sot/interfaces.py.py/update")
        logging.debug(f'unnamed: {unnamed} named: {named}')
        return self.__update_interface(self.get_properties(*unnamed, **named))

    def set_tags(self, new_tags:set):
        logging.debug("-- entering sot/interfaces.py.py/set_tags")
        return self.add_tags(new_tags, False)

    def add_tags(self, new_tags:set, merge_tags=True):
        logging.debug("-- entering sot/interfaces.py.py/add_tags")
        self.open_nautobot()
        logging.debug(f'setting tags {new_tags} on interface {self._interface_name}')

        if self._device is None:
            logging.error(f'unknown device')
            return None

        interface = self._get_interface_from_nautobot()

        # merge tags: merge old and new one
        # if merge is false only the new tags are published to the interface
        if merge_tags:
            for tag in interface.tags:
                new_tags.add(tag.name)

        logging.debug(f'current tags: {interface.tags}')
        logging.debug(f'updating tags to {new_tags}')

        # check if new tag is known
        for new_tag in new_tags:
            tag = self._sot.central.get_entity(self._nautobot.extras.tags,
                                     "Tag",
                                     {'name': new_tag},
                                     {'name': new_tag})
            if tag is None:
                logging.error(f'unknown tag {new_tag}')
                new_tags.remove(new_tag)

        properties = {'tags': list(new_tags)}
        logging.debug(f'final list of tags {properties}')
        # getter to get the interface; we use the device id!
        getter = {'device_id': self._device.id, 'id': interface.id}
        return self._sot.central.update_entity(self._nautobot.dcim.interfaces,
                                     properties,
                                     'Tags',
                                     properties,
                                     getter)

    # -----===== attributes =====-----

    def set_device(self, device):
        self._device = device
        return self

    def use_defaults(self, use_defaults):
        logging.debug(f'setting use_defaults to {use_defaults} (interface)')
        self._use_defaults = use_defaults
        return self

    def return_interface(self, return_interface):
        # return_interface == True: return interface instead of None if device
        # is already part of sot
        logging.debug(f'setting _return_interface to {return_interface}')
        self.return_interface = return_interface
        return self

    # -----===== Interface Management =====-----

    def __add_interface(self, interface):
        logging.debug("-- entering sot/interfaces.py.py/__add_interface")
        self.open_nautobot()
        print(interface)
        # return self._sot.central.add_entity(func=self._nautobot.dcim.interfaces,
        #                                     properties=interface,
        #                                     title="Interface",
        #                                     message={'name': self._interface_name},
        #                                     getter={'name': self._interface_name},
        #                                     return_entity=self._return_interface,
        #                                     convert_id=False)

        return self._sot.central.add_entity_fast(func=self._nautobot.dcim.interfaces,
                                            properties=interface)

    def __update_interface(self, interface):
        logging.debug("-- entering sot/interfaces.py.py/__update_interface")
        self.open_nautobot()
        return self._sot.central.update_entity(func=self._nautobot.dcim.interfaces,
                                               properties=interface,
                                               title="Interface",
                                               message={'name': self._interface_name},
                                               getter={'name': self._interface_name},
                                               convert_id=False)
