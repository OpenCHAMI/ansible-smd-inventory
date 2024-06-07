#!/usr/bin/env python3

from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.errors import AnsibleParserError


DOCUMENTATION = r'''
    name: smd_inventory
    plugin_type: inventory
    short_description: Populates inventory from an smd server
    description: Contacts the specified smd server, performs an inventory lookup, and makes relevant hosts available to Ansible
    options:
      plugin:
        description: Name of the plugin
        required: true
        choices: ['smd_inventory']
      smd_server:
        description: Base address of the smd server to query for inventory
        required: true
'''

EXAMPLES = r'''
    # query the smd server specified in smd_inventory_config.yml, and run a play
    # ansible -i smd_inventory_config.yml play.yml
'''


class InventoryModule(BaseInventoryPlugin):
    NAME = 'smd_inventory'

    def verify_file(self, path: str):
        # We can try to use an inventory file if it a) exists, and b) is YAML
        if super().verify_file(path):
            return path.endswith('yaml') or path.endswith('yml')
        return False

    def parse(self, inventory, loader, path, cache=True):
        super().parse(inventory, loader, path, cache)

        # Parse 'common format' inventory sources and update any options
        # declared in DOCUMENTATION
        config = self._read_config_data(path)
        # TODO: What's `config`, exactly?

        # TODO: Implement smd querying and data parsing (the "real" work)
