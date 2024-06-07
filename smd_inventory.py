#!/usr/bin/env python3

import sys
from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.errors import AnsibleParserError
import requests


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


def get_smd(host: str, endpoint: str, base_path="/hsm/v2/", access_token=None, timeout=10):
    """
    Query an smd endpoint on the specified server.

    Allows overriding the default access token (or lack thereor), base path,
    and timeout. The base path should have both leading and trailing slashes,
    while the hostname and endpoint should not.
    """
    url = host + base_path + endpoint
    headers = None
    if access_token:
        headers = {'Authorization' : f'Bearer {access_token}'}
    r = requests.get(url, headers=headers, timeout=timeout)
    try:
        data = r.json()
        return data
    except requests.exceptions.RequestException:
        tip = ""
        if r.status_code == 401:
            tip = "Please check your access token"
            ret = 65
        else:
            ret = 64
        print(f"Error: {r.status_code} {r.reason} when querying {url}. {tip}")
        sys.exit(ret)
