#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2018, Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'network'}


DOCUMENTATION = """
---
module: interfaces
version_added: "2.8"
short_description: Collect device capabilities from Network devices
description:
  - Collect basic fact capabilities from Network devices and return
    the capabilities as Ansible facts.
author:
  - Trishna Guha (@trishnaguha)
options: {}
"""

EXAMPLES = """
- interfaces:
"""

RETURN = """
"""


from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection, ConnectionError
from ansible.module_utils.cisco_nxos.config.interfaces.interfaces import Interface


def main():
    """ main entry point for module execution
    """
    module = AnsibleModule(argument_spec=Interface.argument_spec,
                           supports_check_mode=True)

    connection = Connection(module._socket_path)
    try:
        config = connection.get('show running-config all | section ^interface')
    except ConnectionError:
        config = None

    result = {'changed': False}
    commands = list()

    intf = Interface(**module.params)

    resp = intf.set_config(module, config)
    if resp:
        commands.extend(resp)

    if commands:
        if not module.check_mode:
            connection.edit_config(commands)
        result['changed'] = True

    result['commands'] = commands
    if result['changed']:
        failed_conditions = intf.set_state(module)

        if failed_conditions:
            msg = 'One or more conditional statements have not been satisfied'
            module.fail_json(msg=msg, failed_conditions=failed_conditions)

    module.exit_json(**result)


if __name__ == '__main__':
    main()
