# Ansible Dynamic Inventory via SMD

This is an Ansible plugin which implements dynamic inventory, by integrating with [smd](https://github.com/OpenCHAMI/smd) (which maintains its own list of nodes and their states).
As a result, the the need to explicitly maintain an Ansible inventory is removed, and smd becomes the relevant source of truth.


## Demo

A traditional call to the smd API, via curl:
```sh
$ curl -s 'https://localhost:27779/hsm/v2/State/Components?type=Node&role=Compute&state=Ready' | jq
{
  "Components": [
    {
      "ID": "x1000c1s7b8n0",
      "Type": "Node",
      "State": "Ready",
      "Flag": "OK",
      "Enabled": true,
      "Role": "Compute",
      "NID": 9,
      "Arch": "X86"
    },
    ...
    {
      "ID": "x1000c1s7b1n0",
      "Type": "Node",
      "State": "Ready",
      "Flag": "OK",
      "Enabled": true,
      "Role": "Compute",
      "NID": 2,
      "Arch": "X86"
    }
  ]
}
```

Exposing smd components as native Ansible inventory, via this plugin:
```sh
$ ansible-inventory --graph -i smd_plugin_inventory.yml -v
...
Using inventory plugin 'smd_inventory' to process inventory source '/home/lritzdorf/smd_plugin_inventory.yml'
Parsed smd component filters {'type': 'Node', 'role': 'Compute', 'state': 'Ready'}
Access token loaded from $ACCESS_TOKEN
Retrieving inventory from smd...
smd component query returned 8 components
smd membership query returned 8 components
Flattened membership to 0 partitions, 0 groups
Populating Ansible inventory...
@all:
  |--@ungrouped:
  |  |--nid009
  |  |--nid008
  |  |--nid007
  |  |--nid006
  |  |--nid005
  |  |--nid004
  |  |--nid003
  |  |--nid002
```


## Features

During inventory creation, additional data from smd is exposed to Ansible for possible use in playbooks and the like.

### Partitions and Groups

Component partitions and groups from smd are exposed as Ansible host groups.
Ansible groups corresponding to smd partitions are prefixed with `prt_`, while Ansible groups corresponding to smd groups are prefixed with `grp_`.

The following inventory was created from an smd instance with partitions `p1` and `p2`, and groups `squares`, `rectangles`, and `circles`:
```sh
$ ansible-inventory --graph -i smd_plugin_inventory.yml
@all:
  |--@ungrouped:
  |--@prt_p2:
  |  |--nid009
  |  |--nid008
  |  |--nid007
  |  |--nid006
  |--@prt_p1:
  |  |--nid005
  |  |--nid004
  |  |--nid003
  |  |--nid002
  |--@grp_squares:
  |  |--nid007
  |  |--nid006
  |--@grp_circles:
  |  |--nid009
  |--@grp_rectangles:
  |  |--nid008
  |  |--nid007
  |  |--nid006
```

### smd Component Data

Each node's smd component, along with its partition/group memberships, is stored under the `smd_component` host variable:
```sh
$ ansible-inventory --list -i smd_plugin_inventory.yml
{
    "_meta": {
        "hostvars": {
            "nid002": {
                "smd_component": {
                    "Arch": "X86",
                    "Enabled": true,
                    "Flag": "OK",
                    "ID": "x1000c1s7b1n0",
                    "NID": 2,
                    "Role": "Compute",
                    "State": "Ready",
                    "Type": "Node",
                    "groupLabels": [],
                    "id": "x1000c1s7b1n0",
                    "partitionName": "p1"
                }
            },
            "nid003": {
                "smd_component": {
                    "Arch": "X86",
                    "Enabled": true,
                    "Flag": "OK",
                    "ID": "x1000c1s7b2n0",
                    "NID": 3,
                    "Role": "Compute",
                    "State": "Ready",
                    "Type": "Node",
                    "groupLabels": [],
                    "id": "x1000c1s7b2n0",
                    "partitionName": "p1"
                }
            },
            ...
```


## Example Inventory

The following inventory file was used to create the examples above:
```yml
---
plugin: smd_inventory
#smd_server: http://localhost:27779
#filter_by: "{'type': 'Node', 'role': 'Compute', 'state': 'Ready'}"
#access_token_envvar: ACCESS_TOKEN
nid_length: 3
```
Commented lines are default values, and will be auto-populated by Ansible if omitted.
