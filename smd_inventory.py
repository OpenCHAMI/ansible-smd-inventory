#!/usr/bin/env python3

import sys
from typing import Any
from ansible.plugins.inventory import BaseInventoryPlugin
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
        type: string
        required: true
      access_token:
        description: Access token for the smd server, if required
        type: string
'''
# TODO: Support multiple smd servers? Would this realistically be useful?

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

    def parse(self, inventory: Any, loader: Any, path: Any, cache: bool = True) -> Any:
        super().parse(inventory, loader, path, cache)

        # Parse 'common format' inventory sources and update any options
        # declared in DOCUMENTATION (retrievable via `get_option()`)
        self._read_config_data(path)

        # Query the smd server to retrieve its node list
        # TODO: How is this formatted? What data does is actually contain?
        the_heck_is_this = get_smd(
                self.get_option('smd_server'),
                "State/Components",
                access_token=self.get_option('access_token'))
                # TODO: What happens if no access token was set? We want the
                # result to be falsy (ideally None).

        # Parse the returned smd inventory and make it available to Ansible
        # TODO: Actually loop over the results from smd
        self.inventory.add_host('the_node_name')
        self.inventory.set_variable('the_node_name', 'ansible_host', 'the_node_ip')


def get_smd(host: str, endpoint: str, base_path="/hsm/v2/", access_token=None, timeout=10):
    """
    Query an smd endpoint on the specified server.

    Allows overriding the default access token (or lack thereof), base path,
    and timeout. The base path should have both leading and trailing slashes,
    while the hostname and endpoint should not.
    """
    url = "https://" + host + base_path + endpoint
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
