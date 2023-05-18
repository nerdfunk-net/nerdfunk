import logging
import json
from pynautobot import api
from pynautobot.models.dcim import Devices
from pynautobot.models.dcim import Interfaces


class Interface:

    # constant values
    _interface_mandatory_properties = ['name', 'description', 'status', 'type']
    _interface_default_values = {'description': '',
                                 'status': 'active',
                                 'type': '1000base-t'}

    def __init__(self, interface_name, sot, device=None):
        logging.debug("-- entering sot/interfaces.py.py/__init__")
        logging.debug(f'initializing interface {interface_name} on {device}')
        # init variables
        self._use_defaults = False

        # interface properties
        self._interface_name = None
        self._interface_obj = None
        self._interface_properties = {}

        # connection to nautobot
        self._nautobot = None

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

    def _get_properties(self, *unnamed, **named):
        logging.debug("-- entering sot/interfaces.py/_get_properties")
        properties = self.__convert_arguments_to_properties(*unnamed, **named)

        if 'name' not in properties:
            properties['name'] = self._interface_name
        logging.debug(f'add interface: {self._interface_name}')

        if self._use_defaults:
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

    # -----===== user commands =====----- 

    def get(self):
        logging.debug("-- entering sot/interfaces.py/get")
        if self._interface_obj is None:
            return self._get_interface_from_nautobot()
        return self._interface_obj

    def set_tags(self, new_tags:set):
        logging.debug("-- entering sot/interfaces.py/set_tags")
        return self.add_tags(new_tags, False)

    def add_tags(self, new_tags:set, merge_tags=True):
        logging.debug("-- entering sot/interfaces.py/add_tags")
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
            tag = self._sot.central.get_entity(self._nautobot.extras.tags, "Tag", {'name': new_tag})
            if tag is None:
                logging.error(f'unknown tag {new_tag}')
                new_tags.remove(new_tag)

        properties = {'tags': list(new_tags)}
        logging.debug(f'final list of tags {properties}')
        # getter to get the interface; we use the device id!
        getter = {'device_id': self._device.id, 'id': interface.id}
        return self._sot.central.update_entity(self._nautobot.dcim.interfaces,
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

    # -----===== Interface Management =====-----

    def add(self, *unnamed, **named):
        logging.debug("-- entering sot/interfaces.py/add")
        self.open_nautobot()

        properties = self._get_properties(*unnamed, **named)
        return self._sot.central.add_entity(func=self._nautobot.dcim.interfaces,
                                            properties=properties)

    def update(self, *unnamed, **named):
        logging.debug("-- entering sot/interfaces.py.py/update")
        self.open_nautobot()

        properties = self.__convert_arguments_to_properties(*unnamed, **named)
        return self._sot.central.update_entity(func=self._nautobot.dcim.interfaces,
                                               properties=properties,
                                               getter={'name': self._interface_name},
                                               convert_id=False)
