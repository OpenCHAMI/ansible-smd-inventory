# Ansible Dynamic Inventory via SMD

This is an Ansible plugin which implements dynamic inventory, by integrating with [smd](https://github.com/OpenCHAMI/smd) (which maintains its own list of nodes and their states).
As a result, the the need to explicitly maintain an Ansible inventory is removed, and smd becomes the relevant source of truth.


## Demo

A traditional call to the smd API, via curl:
```sh
$ curl -s 'https://localhost:27779/hsm/v2/State/Components?type=Node&role=Compute&state=Ready' | jq '.Components[] | {xname: .ID, NID: .NID}'
{
  "xname": "x1000c1s7b8n0",
  "NID": 9
}
...
{
  "xname": "x1000c1s7b2n0",
  "NID": 3
}
{
  "xname": "x1000c1s7b1n0",
  "NID": 2
}
```

Exposing smd components as native Ansible inventory, via this plugin:
```sh
$ ansible-inventory --graph -i smd_plugin_inventory.yml -vvv
...
Using inventory plugin 'smd_inventory' to process inventory source '/home/lritzdorf/smd_plugin_inventory.yml'
Access token loaded from $ACCESS_TOKEN
smd query with filter {'type': 'Node', 'role': 'Compute', 'state': 'Ready'} returned 8 components
Adding component x1000c1s7b8n0 as nid009...
Adding component x1000c1s7b7n0 as nid008...
Adding component x1000c1s7b6n0 as nid007...
Adding component x1000c1s7b5n0 as nid006...
Adding component x1000c1s7b4n0 as nid005...
Adding component x1000c1s7b3n0 as nid004...
Adding component x1000c1s7b2n0 as nid003...
Adding component x1000c1s7b1n0 as nid002...
Parsed /home/lritzdorf/smd_plugin_inventory.yml inventory source with auto plugin
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

**Coming soon:** Exposing smd partitions and groups as Ansible host groups!

The complete structure of the smd component is stored under the `smd_component` host variable:
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
                    "Type": "Node"
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
                    "Type": "Node"
                }
            },
            ...
        }
    },
    "all": {
        "children": [
            "ungrouped"
        ]
    },
    "ungrouped": {
        "hosts": [
            "nid009",
            "nid008",
            "nid007",
            "nid006",
            "nid005",
            "nid004",
            "nid003",
            "nid002"
        ]
    }
}
```


## Example Inventory

The following inventory file was used to create the examples above:
```yml
---
plugin: smd_inventory
#smd_server: localhost:27779
#filter_by: "{'type': 'Node', 'role': 'Compute', 'state': 'Ready'}"
#access_token_envvar: ACCESS_TOKEN
nid_length: 3
```
Commented lines are default values, and will be auto-populated by Ansible if omitted.
