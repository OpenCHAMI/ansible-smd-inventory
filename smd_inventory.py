#!/usr/bin/env python3

from typing import Any
from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.errors import AnsibleParserError
from json import loads as json_loads
from os import getenv
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
        default: 'localhost:27779'
      filter_by:
        description: smd filter parameters to apply
        type: string
        default: '{"type": "Node", "role": "Compute", "state": "Ready"}'
      access_token_envvar:
        description: Environment variable from which to retrieve smd access token, if required
        type: string
        default: 'ACCESS_TOKEN'
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

    def __init__(self):
        super().__init__()
        self.smd_server = None
        self.filter_by = {}
        self.access_token = None

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

        try:
            # Retrieve and store config options
            self.smd_server = self.get_option('smd_server')
            self.filter_by = json_loads(self.get_option('filter_by'))
            access_token_envvar = self.get_option('access_token_envvar')
            if access_token_envvar:
                self.access_token = getenv(access_token_envvar)
                if not self.access_token:
                    self.display.warning(
                            f"Expected to find an access token in ${access_token_envvar}, but it was empty/unset. "
                            "This may cause smd API calls to fail if the endpoint requires authentication")
                else:
                    self.display.v(f"Access token loaded from ${access_token_envvar}")
            else:
                self.display.v("No access token environment variable specified; skipping...")

        except KeyError as e:
            # Handle unset config optons
            raise AnsibleParserError(
                    f"Please ensure that all required options in config file \"{path}\" are set",
                    e) from e

        except AnsibleParserError: raise  # Pass through errors that are already of the correct form

        except Exception as e:
            self.display.error(repr(e))
            raise AnsibleParserError(
                    "An error occurred during inventory loading from smd",
                    e) from e

        # Populate the inventory from smd
        self.populate_inventory_smd()
        # TODO: Load smd groups as Ansible groups?


    def populate_inventory_smd(self):
        # Query the smd server to retrieve its component list
        components = get_smd(self.smd_server, "State/Components", params=self.filter_by,
                             access_token=self.access_token
                             )['Components']
        self.display.v(f"smd query with filter {self.filter_by} returned {len(components)} components")

        # Make each component from smd available to ansible
        for component in components:
            nid_name = 'nid' + str(component['NID']).zfill(self.get_option('nid_length'))
            self.display.vvv(f"Adding component {component['ID']} as {nid_name}...")
            self.inventory.add_host(nid_name)
            # Load a host variable with the state from smd, in case it's needed later
            self.inventory.set_variable(nid_name, 'smd_component', component)

        return inventory


def get_smd(host: str, endpoint: str, params: dict|None = None,
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
    r = requests.get(url, params=params, headers=headers)
    try:
        data = r.json()
        return data
    except requests.exceptions.RequestException as e:
        tips = {200: "Please check your API endpoint",
                401: "Please check your access token"}
        print(f"Error: {r.status_code} {r.reason} when querying {url}.",
              tips.get(r.status_code, ""))
        raise


if __name__ == "__main__":
    import sys
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
                     params={"type": "Node", "role": "Compute", "state": "Ready"},
                     access_token=access_token)
    for component in result['Components']:
        print("Found {Type} {ID} with NID {NID}".format(**component))
