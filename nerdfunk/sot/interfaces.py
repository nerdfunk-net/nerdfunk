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
        logging.debug(f'initializing interface {interface_name} on {device} (interface.py)')
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

    # -----===== user commands =====----- 

    def get(self):
        if self._interface_obj is None:
            return self._get_interface_from_nautobot()
        return self._interface_obj

    def add(self, *unnamed, **named):
        # unnamed args are always a list; we use the first item only; we aspect a dict here
        # named args is a dict
        interface_properties = dict(named)
        if unnamed:
            interface_properties.update(unnamed[0])
        interface_properties['name'] = self._interface_name
        logging.debug(f'add interface: {self._interface_name} use_defaults: {self._use_defaults}')

        for key in self._interface_mandatory_properties:
            if key not in interface_properties:
                if self._use_defaults:
                    logging.error(f'mandatory property {key} is missing; using default')
                    interface_properties[key] = self._interface_default_values.get(key)
                else:
                    logging.error(f'mandatory property {key} is missing')
                    return False

        return self.__add_interface(interface_properties)

    def set_tags(self, new_tags:set):
        return self.add_tags(new_tags, False)

    def add_tags(self, new_tags:set, merge_tags=True):
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
        self.open_nautobot()
        nb_interface = self._nautobot.dcim.interfaces.get(
            device_id=self._device.id,
            name=interface['name']
        )

        if nb_interface is not None:
            logging.info("interface %s already exists" % self._interface_name)
            if self._return_interface:
                return nb_interface
            else:
                return None
        else:
            logging.debug("converting properties to IDs")
            logging.debug(interface)
            success, error = self._sot.central.get_ids(interface)
            if not success:
                logging.error(f'could not convert properties to IDs; {error}')
                return False

            # try:
            interface['device'] = self._device.id
            logging.debug(interface)
            nb_interface = self._nautobot.dcim.interfaces.create(interface)
            self._interface_obj = nb_interface
            logging.debug("added new interface %s/%s" % (self._device.name, self._interface_name))
            return nb_interface

