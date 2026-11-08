variable "libvirt_uri" { type = string; default = "qemu:///system" }
variable "storage_pool" { type = string; default = "default" }
variable "network_name" { type = string; default = "virbr0" }
variable "job_name" { type = string }
variable "nodes" { type = list(any) }
