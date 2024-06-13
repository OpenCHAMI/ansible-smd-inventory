#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: Triad National Security, LLC
# MIT License

DOCUMENTATION = r'''
    module: smd_inventory
    short_description: Populates inventory from an smd server.
    description: Contacts the specified smd server, performs a component lookup, and makes relevant components available to Ansible as inventory.
    author: Lucas Ritzdorf (lritzdorf@lanl.gov)
    options:
      plugin:
        description: Name of this plugin. Causes the inventory file to be parsed by us, rather than a different plugin.
        required: true
        choices: ['smd_inventory']
      smd_server:
        description: Base address of the smd server to query for inventory, without a trailing slash.
        type: string
        default: 'localhost:27779'
      filter_by:
        description: smd filter parameters to apply when querying components.
        type: string
        default: '{"type": "Node", "role": "Compute", "state": "Ready"}'
      access_token_envvar:
        description: Environment variable containing a valid access token, if required by your smd server.
        type: string
        default: 'ACCESS_TOKEN'
      nid_length:
        description: Number of digits in the cluster's node IDs. For example, "nid042" has three digits.
        type: integer
        default: 6
    notes:
      - This plugin will query the smd endpoints C(/State/Components) and C(/memberships).
        If these require an access token, ensure that O(access_token_envvar) is set appropriately.
      - Providing your own filter parameters (O(filter_by)) will replace the defaults, so you may want to use them as a starting point.
      - Component data retrieved from smd is stored in the C(smd_component) host variable on a per-host basis.
        It contains a dictionary, which unions the fields returned by the queried API endpoints (ID, Arch, Flag...).
    seealso:
      - name: OpenCHAMI smd Fork
        description: The OpenCHAMI group's fork of the State Management Database (smd) project.
        link: https://github.com/OpenCHAMI/smd
      - name: HPE smd Base Project
        description: The original HPE version of the State Management Database (smd) project.
        link: https://github.com/Cray-HPE/hms-smd
    extends_documentation_fragment:
      - inventory_cache
'''
# TODO: Support construction? Does this plugin even need to be concerned with that?
# See https://docs.ansible.com/ansible/latest/dev_guide/developing_inventory.html#constructed-features

EXAMPLES = r'''
Use with an appropriate inventory configuration file.

To query an smd server as specified in smd_inventory_config.yml, and run a play:
$ ansible-playbook play.yml -i smd_inventory_config.yml

Default options correspond to the following configuration file:
---
plugin: smd_inventory
smd_server: localhost:27779
filter_by: "{'type': 'Node', 'role': 'Compute', 'state': 'Ready'}"
access_token_envvar: ACCESS_TOKEN
nid_length: 6
'''

RETURN = r''' # '''


from typing import Any
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable
from ansible.errors import AnsibleError, AnsibleParserError
from json import loads as json_loads
from os import getenv
import requests


class InventoryModule(BaseInventoryPlugin, Cacheable):
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
        # declared in DOCUMENTATION (retrievable via `get_option()`) and load
        # the cache.
        self._read_config_data(path)
        cache_key = self.get_cache_key(path)

        try:
            # Retrieve and store config options
            self.smd_server = self.get_option('smd_server')
            self.filter_by = json_loads(self.get_option('filter_by'))
            self.display.v(f"Parsed smd component filters {self.filter_by}")
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

        # Retrieve or load inventory, while interacting with the cache; see
        # https://docs.ansible.com/ansible/latest/dev_guide/developing_inventory.html#inventory-cache
        user_cache_setting = self.get_option('cache')
        attempt_to_read_cache = user_cache_setting and cache
        cache_needs_update = user_cache_setting and not cache

        if attempt_to_read_cache:
            try:
                self.display.v("Attempting to read inventory from cache...")
                inventory = self._cache[cache_key]
            except KeyError:
                self.display.v("Cache read failed; needs update")
                cache_needs_update = True

        if not attempt_to_read_cache or cache_needs_update:
            self.display.v("Retrieving inventory from smd...")
            inventory = self.get_inventory()

        if cache_needs_update:
            self.display.v("Caching inventory...")
            self._cache[cache_key] = inventory

        self.display.v("Populating Ansible inventory...")
        self.populate(**inventory)


    def get_inventory(self) -> dict[str, dict]:
        """
        Query smd to obtain a list of components and their memberships
        """

        # Retrieve the filtered component inventory from smd...
        response = self.get_smd(self.smd_server, "State/Components", params=self.filter_by)
        # ...and build a dictionary indexed by "IDs" (xnames)
        try:
            components = {comp['ID']: comp for comp in response['Components']}
        except KeyError:
            raise AnsibleParserError("smd component response does not match expected format. Check your access token?")
        self.display.v(f"smd component query returned {len(components)} components")

        # Retrieve the filtered components' membership data from smd
        memberships = self.get_smd(self.smd_server, "memberships", params=self.filter_by)
        self.display.v(f"smd membership query returned {len(components)} components")
        # Merge into the existing component data, and extract partition/group sets
        partitions, groups = set(), set()
        try:
            for comp in memberships:
                components[comp['id']].update(comp)
                if comp['partitionName']:
                    partitions.add(comp['partitionName'])
                if comp['groupLabels']:
                    groups.update(comp['groupLabels'])
        except KeyError:
            raise AnsibleParserError("smd membership response does not match expected format. Check your access token?")

        # Done!
        self.display.v(f"Flattened membership to {len(partitions)} partitions, {len(groups)} groups")
        return {'components': components, 'partitions': partitions, 'groups': groups}


    def populate(self, components: dict[str, dict[str, str]], partitions: set[str], groups: set[str]):
        """
        Use an inventory dump from smd to populate the Ansible inventory
        """

        # Create all relevant groups ahead-of-time
        try:
            self.display.vv(f"Adding partitions {partitions}...")
            for partition in partitions:
                self.inventory.add_group('prt_' + partition)
            self.display.vv(f"Adding groups {groups}...")
            for group in groups:
                self.inventory.add_group('grp_' + group)
        except AnsibleError as e:
            raise AnsibleParserError(f"Unable to add a group: {repr(e)}") from e

        # Make each inventory component from smd available to Ansible
        for component in components:
            # Reformat NID and partition name (if any); actually add the host
            nid_name = 'nid' + str(component['NID']).zfill(self.get_option('nid_length'))
            if component['partitionName']:
                partition_name = 'prt_' + component['partitionName']
                self.display.vv(f"Adding component {component['ID']} as {nid_name} in {partition_name}...")
                self.inventory.add_host(nid_name, partition_name)
            else:
                self.display.vv(f"Adding component {component['ID']} as {nid_name} without partition...")
                self.inventory.add_host(nid_name)

            # Add each host to its other groups
            for group in component['groupLabels']:
                group_name = 'grp_' + group
                self.display.vvv(f"Adding component {component['ID']} to {group_name}...")
                self.inventory.add_host(nid_name, group_name)

            # Load a host variable with the state from smd, for use in Ansible
            self.inventory.set_variable(nid_name, 'smd_component', component)


    def get_smd(self, host: str, endpoint: str, params: dict|None = None,
                base_path: str = "/hsm/v2/"):
        """
        Query an smd endpoint on the specified server.

        Allows overriding the default access token (or rather, lack thereof) and
        API base path. The base path should have both leading and trailing slashes,
        while the hostname and endpoint should have neither.
        """
        url = "https://" + host + base_path + endpoint
        headers = None
        if self.access_token:
            headers = {'Authorization' : f'Bearer {self.access_token}'}
        r = requests.get(url, params=params, headers=headers)
        try:
            data = r.json()
            return data
        except requests.exceptions.RequestException as e:
            tips = {200: "Please check your API endpoint",
                    401: "Please check your access token"}
            raise AnsibleParserError(
                    f"Error: {r.status_code} {r.reason} when querying {url}. {tips.get(r.status_code, '')}",
                    e) from e
