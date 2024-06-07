# Ansible Dynamic Inventory via SMD

This is an Ansible plugin which implements dynamic inventory, by integrating with [smd](https://github.com/OpenCHAMI/smd) (which maintains its own list of nodes and their states).
As a result, the the need to explicitly maintain an Ansible inventory is removed, and smd becomes the relevant source of truth.
