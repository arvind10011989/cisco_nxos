import re

from time import sleep

from ansible.module_utils.connection import Connection
from ansible.module_utils.network.common.utils import conditional, to_list
from ansible.module_utils.cisco_nxos.config import ConfigBase


class Interface(ConfigBase):

    config_extensions_spec = {
        'mode': dict(choices=['layer2', 'layer3']),
        'ip_forward': dict(choices=['enable', 'disable']),
        'fabric_forwarding_anycast_gateway': dict(type='bool'),
    }

    state_extensions_spec = {
    }

    config_spec = {
        'name': dict(required=True),
        'description': dict(),
        'enable': dict(type=bool),
        'speed': dict(),
        'mtu': dict(),
        'duplex': dict(choices=['full', 'half', 'auto']),
        'state': dict(default='present', choices=['present', 'absent']),
        'extensions': dict(default={}, type='dict', elements='dict', options=config_extensions_spec)
    }

    neighbors_spec = {
        'host': dict(),
        'port': dict()
    }

    state_spec = {
        'name': dict(),
        'status': dict(choices=['up', 'down']),
        'tx_rate': dict(),
        'rx_rate': dict(),
        'delay': dict(default=10, type='int'),
        'neighbors': dict(default={}, type='dict', elements='dict', options=neighbors_spec),
        'extensions': dict(default={}, type='dict', elements='dict', options=state_extensions_spec)
    }

    argument_spec = {
        'operation': dict(default='merge', choices=['merge', 'replace', 'override']),
        'config': dict(default={}, type='dict', elements='dict', options=config_spec),
        'state': dict(default={}, type='dict', elements='dict', options=state_spec)
    }

    def parse_config_argument(self, cfg, arg):
        match = re.search(r'%s (.+)(\n|$)' % arg, cfg, re.M)
        if match:
            return match.group(1).strip()
        return None

    def set_config(self, module, config):
        name = self.normalize_interface(self.config['name'])
        want = self._config_map_params_to_obj(module, name)
        have = self._config_map_conf_to_obj(module, config)

        resp = self.set_operation(module, want, have)
        return to_list(resp)

    def set_operation(self, module, want, have):
        commands = list()

        operation = self.operation
        if operation == 'override':
            commands.extend(self._operation_override(module, want, have))
        else:
            for w in want:
                name = w['name']
                interface_type = self.get_interface_type(name)
                obj_in_have = self.search_obj_in_list(name, have)
                state = w['state']
                if state == 'absent' and operation == 'replace':
                    module.fail_json(msg='state: absent can only be used with operation: merge')

                if operation == 'merge':
                    if state == 'absent':
                        if obj_in_have:
                            commands.append('no interface {0}'.format(w['name']))
                    if state == 'present':
                        commands.extend(self.state_present(module, w, obj_in_have, interface_type))

                if operation == 'replace':
                    commands.extend(self._operation_replace(module, w, obj_in_have, interface_type))

        return commands

    def _operation_replace(self, module, w, obj_in_have, interface_type):
        commands = list()

        if interface_type in ('loopback', 'portchannel', 'svi'):
            commands.append('no interface {0}'. format(w['name']))
            commands.extend(self.state_present(module, w, obj_in_have, interface_type))
        else:
            commands.append('default interface {0}'.format(w['name']))
            commands.extend(self.state_present(module, w, obj_in_have, interface_type))

        return commands

    def _operation_override(self, module, want, have):
        """
        purge interfaces
        """
        commands = list()

        for h in have:
            name = h['name']
            obj_in_want = self.search_obj_in_list(name, want)
            if not obj_in_want:
                interface_type = self.get_interface_type(name)

                # Remove logical interfaces
                if interface_type in ('loopback', 'portchannel', 'svi'):
                    commands.append('no interface {0}'.format(name))
                elif interface_type == 'ethernet':
                    # Put physical interface back into default state
                    commands.append('default interface {0}'.format(name))

        for w in want:
            name = w['name']
            state = w['state']
            if state == 'absent':
                module.fail_json(msg='state: absent can only be used with operation: merge')

            interface_type = self.get_interface_type(name)
            obj_in_have = self.search_obj_in_list(name, have)
            commands.extend(self.state_present(module, w, obj_in_have, interface_type))

        return commands

    def state_present(self, module, w, obj_in_have, interface_type):
        commands = list()

        args = ('speed', 'description', 'duplex', 'mtu')
        name = w['name']
        mode = w['mode']
        ip_forward = w['ip_forward']
        fabric_forwarding_anycast_gateway = w['fabric_forwarding_anycast_gateway']
        enable = w['enable']
        del w['state']

        if name:
            interface = 'interface ' + name

        if not obj_in_have:
            commands.append(interface)
            if interface_type in ('ethernet', 'portchannel'):
                if mode == 'layer2':
                    commands.append('switchport')
                elif mode == 'layer3':
                    commands.append('no switchport')

            if enable is True:
                commands.append('no shutdown')
            elif enable is False:
                commands.append('shutdown')

            if ip_forward == 'enable':
                commands.append('ip forward')
            elif ip_forward == 'disable':
                commands.append('no ip forward')

            if fabric_forwarding_anycast_gateway is True:
                commands.append('fabric forwarding mode anycast-gateway')
            elif fabric_forwarding_anycast_gateway is False:
                commands.append('no fabric forwarding mode anycast-gateway')

            for item in args:
                candidate = w.get(item)
                if candidate:
                    commands.append(item + ' ' + str(candidate))

        else:
            if interface_type in ('ethernet', 'portchannel'):
                if mode == 'layer2' and mode != obj_in_have.get('mode'):
                    self.add_command_to_interface(interface, 'switchport', commands)
                elif mode == 'layer3' and mode != obj_in_have.get('mode'):
                    self.add_command_to_interface(interface, 'no switchport', commands)

            if enable is True and enable != obj_in_have.get('enable'):
                self.add_command_to_interface(interface, 'no shutdown', commands)
            elif enable is False and enable != obj_in_have.get('enable'):
                self.add_command_to_interface(interface, 'shutdown', commands)

            if ip_forward == 'enable' and ip_forward != obj_in_have.get('ip_forward'):
                self.add_command_to_interface(interface, 'ip forward', commands)
            elif ip_forward == 'disable' and ip_forward != obj_in_have.get('ip forward'):
                self.add_command_to_interface(interface, 'no ip forward', commands)

            if (fabric_forwarding_anycast_gateway is True and obj_in_have.get('fabric_forwarding_anycast_gateway') is False):
                self.add_command_to_interface(interface, 'fabric forwarding mode anycast-gateway', commands)

            elif (fabric_forwarding_anycast_gateway is False and obj_in_have.get('fabric_forwarding_anycast_gateway') is True):
                self.add_command_to_interface(interface, 'no fabric forwarding mode anycast-gateway', commands)

            for item in args:
                candidate = w.get(item)
                if candidate and candidate != obj_in_have.get(item):
                    cmd = item + ' ' + str(candidate)
                    self.add_command_to_interface(interface, cmd, commands)

            # if the mode changes from L2 to L3, the admin state
            # seems to change after the API call, so adding a second API
            # call to ensure it's in the desired state.
            if name and interface_type == 'ethernet':
                if mode and mode != obj_in_have.get('mode'):
                    enable = w.get('enable') or obj_in_have.get('enable')
                    if enable is True:
                        commands.append(self._get_admin_state(enable))

        return commands

    def _get_admin_state(self, enable):
        command = ''
        if enable is True:
            command = 'no shutdown'
        elif enable is False:
            command = 'shutdown'
        return command

    def add_command_to_interface(self, interface, cmd, commands):
        if interface not in commands:
            commands.append(interface)
        commands.append(cmd)

    def _config_map_params_to_obj(self, module, name=None):
        obj = []
        extensions = self.config.get('extensions', {})

        obj.append({
            'name': name,
            'description': self.config['description'],
            'enable': self.config['enable'],
            'speed': self.config['speed'],
            'mtu': self.config['mtu'],
            'duplex': self.config['duplex'],
            'state': self.config['state'],
            'mode': extensions.get('mode', None),
            'ip_forward': extensions.get('ip_forward', None),
            'fabric_forwarding_anycast_gateway': extensions.get('fabric_forwarding_anycast_gateway', None),
        })

        return obj

    def _config_map_conf_to_obj(self, module, config):
        objs = []
        if not config:
            return objs

        config = config.split('interface ')[1:]
        for conf in config:
            name = conf.splitlines()[0]

            enable = None
            match = re.search(r'\n\s+no shutdown(\n|$)', conf)
            if match:
                enable = True
            match = re.search(r'\n\s+shutdown(\n|$)', conf)
            if match:
                enable = False

            mode = None
            if self.get_interface_type(name) in ('portchannel', 'ethernet'):
                match = re.search(r'\n\s+switchport(\n|$)', conf)
                if match:
                    mode = 'layer2'
                match = re.search(r'\n\s+no switchport(\n|$)', conf)
                if match:
                    mode = 'layer3'

            fabric_forwarding_anycast_gateway = None
            match = re.search(r'\n\s+fabric forwarding mode anycast-gateway(\n|$)', conf)
            if match:
                fabric_forwarding_anycast_gateway = True
            match = re.search(r'\n\s+no fabric forwarding mode anycast-gateway(\n|$)', conf)
            if match:
                fabric_forwarding_anycast_gateway = False

            ip_forward = None
            match = re.search(r'\n\s+ip forward(\n|$)', conf)
            if match:
                ip_forward = 'enable'
            match = re.search(r'\n\s+no ip forward(\n|$)', conf)
            if match:
                ip_forward = 'disable'

            obj = {
                'name': name,
                'description': self.parse_config_argument(conf, 'description'),
                'enable': enable,
                'speed': self.parse_config_argument(conf, 'speed'),
                'mtu': self.parse_config_argument(conf, 'mtu'),
                'duplex': self.parse_config_argument(conf, 'duplex'),
                'mode': mode,
                'fabric_forwarding_anycast_gateway': fabric_forwarding_anycast_gateway,
                'ip_forward': ip_forward,
            }
            objs.append(obj)

        return objs

    def neighbors_state(self, module, name, config):
        conditions = []

        if config.startswith('ERROR'):
            return conditions

        want = self._state_map_params_to_obj(module, name)
        have_neighbors = self._populate_neighbors(module, config)
        obj_in_have = self.search_obj_in_list(name, have_neighbors)

        if obj_in_have:
            for w in want:
                host = w.get('host')
                port = w.get('port')
                if host and host != obj_in_have['host']:
                    conditions.append('host ' + host)
                if port and port != obj_in_have['port']:
                    conditions.append('port ' + port)

        return conditions

    def _populate_neighbors(self, module, config):
        objects = []
        regex = re.compile(r'(\S+)\s+(\S+)\s+\d+\s+\w+\s+(\S+)')

        for item in config.split('\n')[4:-1]:
            match = regex.match(item)
            if match:
                local_intf = self.normalize_interface(match.group(2))
                neighbor = {'name': local_intf, 'host': match.group(1), 'port': match.group(3)}
                objects.append(neighbor)

        return objects

    def set_state(self, module):
        failed_conditions = []
        if self.operation == 'override':
            return failed_conditions

        name = self.normalize_interface(self.state['name'])
        if not name:
            return failed_conditions

        want = self._state_map_params_to_obj(module, name)
        for w in want:
            status = w.get('status')
            tx_rate = w.get('tx_rate')
            rx_rate = w.get('rx_rate')
            delay = w.get('delay')
            host = w.get('host')
            port = w.get('port')
            sleep(delay)

            lst = [status, tx_rate, rx_rate]
            if all(not i for i in lst):
                return failed_conditions

            _connection = Connection(module._socket_path)
            config = _connection.get('show interface %s' % name)

            if status:
                have_status = None
                match = re.search(r'admin state is (\S+)', config, re.M)
                if match:
                    have_status = match.group(1).strip(',')
                    if status != have_status:
                        failed_conditions.append('status ' + status)

            if tx_rate:
                match = re.search(r'output rate (\d+)', config, re.M)
                have_tx_rate = None
                if match:
                    have_tx_rate = match.group(1)
                if have_tx_rate is None or not conditional(tx_rate, have_tx_rate.strip(), cast=int):
                    failed_conditions.append('tx_rate ' + tx_rate)

            if rx_rate:
                match = re.search(r'input rate (\d+)', config, re.M)
                have_rx_rate = None
                if match:
                    have_rx_rate = match.group(1)
                if have_rx_rate is None or not conditional(rx_rate, have_rx_rate.strip(), cast=int):
                    failed_conditions.append('rx_rate ' + rx_rate)

            if host or port:
                _connection.get('feature lldp')
                config_nbor = _connection.get('show lldp neighbors')
                failed_conditions.extend(self.neighbors_state(module, name, config_nbor))

        return failed_conditions

    def _state_map_params_to_obj(self, module, name=None):
        obj = []
        neighbors = self.state.get('neighbors', {})

        obj.append({
            'name': name,
            'status': self.state['status'],
            'tx_rate': self.state['tx_rate'],
            'rx_rate': self.state['rx_rate'],
            'delay': self.state['delay'],
            'host': neighbors['host'],
            'port': neighbors['port'],
        })

        return obj
