from itertools import chain

from ansible.module_utils.six import iteritems
from ansible.module_utils.network.common.utils import to_list, sort_list
from ansible.module_utils.network.common.config import NetworkConfig


class ConfigBase(object):

    argument_spec = {}
    identifier = ()

    def __init__(self, **kwargs):
        self.values = {}

        for item in self.identifier:
            self.values[item] = kwargs.pop(item)

        for key, value in iteritems(kwargs):
            if key in self.argument_spec:
                setattr(self, key, value)

    def __getattr__(self, key):
        if key in self.argument_spec:
            return self.values.get(key)

    def __setattr__(self, key, value):
        if key in self.argument_spec:
            if key in self.identifier:
                raise TypeError('cannot set value')
            elif value is not None:
                self.values[key] = value
        else:
            super(ConfigBase, self).__setattr__(key, value)

    def render(self, config=None):
        raise NotImplementedError

    def get_section(self, config, section):
        if config is not None:
            netcfg = NetworkConfig(indent=2, contents=config)
            try:
                config = netcfg.get_block_config(to_list(section))
            except ValueError:
                config = None
            return config

    def search_obj_in_list(self, name, lst):
        for o in lst:
            if o['name'] == name:
                return o
        return None

    def normalize_interface(self, name):
        """Return the normalized interface name
        """
        if not name:
            return

        def _get_number(name):
            digits = ''
            for char in name:
                if char.isdigit() or char in '/.':
                    digits += char
            return digits

        if name.lower().startswith('et'):
            if_type = 'Ethernet'
        elif name.lower().startswith('vl'):
            if_type = 'Vlan'
        elif name.lower().startswith('lo'):
            if_type = 'loopback'
        elif name.lower().startswith('po'):
            if_type = 'port-channel'
        elif name.lower().startswith('nv'):
            if_type = 'nve'
        else:
            if_type = None

        number_list = name.split(' ')
        if len(number_list) == 2:
            number = number_list[-1].strip()
        else:
            number = _get_number(name)

        if if_type:
            proper_interface = if_type + number
        else:
            proper_interface = name

        return proper_interface

    def get_interface_type(self, interface):
        """Gets the type of interface
        """
        if interface.upper().startswith('ET'):
            return 'ethernet'
        elif interface.upper().startswith('VL'):
            return 'svi'
        elif interface.upper().startswith('LO'):
            return 'loopback'
        elif interface.upper().startswith('MG'):
            return 'management'
        elif interface.upper().startswith('MA'):
            return 'management'
        elif interface.upper().startswith('PO'):
            return 'portchannel'
        elif interface.upper().startswith('NV'):
            return 'nve'
        else:
            return 'unknown'
