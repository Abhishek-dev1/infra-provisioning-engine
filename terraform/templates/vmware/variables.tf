variable "vsphere_server" { type = string; default = "vcenter.infra.internal" }
variable "vsphere_datacenter" { type = string; default = "Datacenter-Enterprise" }
variable "vsphere_cluster" { type = string; default = "Compute-Cluster-01" }
variable "vsphere_datastore" { type = string; default = "vsanDatastore" }
variable "vsphere_network" { type = string; default = "dvPortGroup-Workloads-VLAN100" }
variable "job_name" { type = string }
variable "nodes" { type = list(any) }
