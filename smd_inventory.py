#!/usr/bin/env python3

import sys
from typing import Any
from ansible.plugins.inventory import BaseInventoryPlugin
import requests


DOCUMENTATION = r'''
    name: smd_inventory
    plugin_type: inventory
    short_description: Populates inventory from an smd server
    description: Contacts the specified smd server, performs a component lookup, and makes relevant components available to Ansible as inventory
    options:
      plugin:
        description: Name of the plugin
        required: true
        choices: ['smd_inventory']
      smd_server:
        description: Base address of the smd server to query for inventory
        type: string
        required: true
      filter_by:
        description: smd filter parameters to apply
        type: string
        default: '{"type": "Node", "role": "Compute", "state": "Ready"}'
      access_token:
        description: Access token for the smd server, if required
        type: string
      nid_length:
        description: number of digits in the cluster's node IDs
        type: integer
        default: 6
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

    def parse(self, inventory: Any, loader: Any, path: Any, cache: bool = True) -> Any:
        super().parse(inventory, loader, path, cache)

        # Parse 'common format' inventory sources and update any options
        # declared in DOCUMENTATION (retrievable via `get_option()`)
        self._read_config_data(path)

        # Query the smd server to retrieve its component list
        # TODO: Load smd groups as Ansible groups?
        result = get_smd(
                self.get_option('smd_server'), "State/Components",
                filter_by=self.get_option('filter_by'),
                access_token=self.get_option('access_token'))

        # Make each component from smd available to ansible
        for component in result['Components']:
            nid_name = 'nid' + component['NID'].zfill(self.get_option('nid_length'))
            self.inventory.add_host(nid_name)
            # TODO: What if we have a cluster with more than 999 nodes? How do we know?
            # Load a host variable with the state from smd, in case it's needed later
            self.inventory.set_variable(nid_name, 'smd_component', component)


def get_smd(host: str, endpoint: str, filter_by: dict,
        base_path="/hsm/v2/", access_token=None):
    """
    Query an smd endpoint on the specified server.

    Allows overriding the default access token (or rather, lack thereof) and
    API base path. The base path should have both leading and trailing slashes,
    while the hostname and endpoint should have neither.
    """
    url = "https://" + host + base_path + endpoint
    headers = None
    if access_token:
        headers = {'Authorization' : f'Bearer {access_token}'}
    r = requests.get(url, params=filter_by, headers=headers)
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


if __name__ == "__main__":
    access_token = None
    # Check arguments: <smd_server> [access_token]
    if len(sys.argv) < 2:
        print("For use in standalone mode, specify smd server to target and optional access token")
        sys.exit(1)
    elif len(sys.argv) == 3:
        access_token = sys.argv[2]
    elif len(sys.argv) > 3:
        print("More than two arguments passed; ignoring extras...")

    # Just list hosts, don't interface with Ansible
    result = get_smd(sys.argv[1], "State/Components",
                     {"type": "Node", "role": "Compute", "state": "Ready"},
                     access_token=access_token)
    for component in result['Components']:
        print("Found {Type} {ID} with NID {NID}".format(**component))
