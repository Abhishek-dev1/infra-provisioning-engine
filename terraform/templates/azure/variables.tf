variable "azure_location" {
  type    = string
  default = "eastus"
}

variable "resource_group_name" {
  type = string
}

variable "job_name" {
  type = string
}

variable "environment" {
  type    = string
  default = "test"
}

variable "ssh_public_key" {
  type    = string
  default = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG5vZGUtcHJvdmlzaW9uZXIta2V5 abhishek@infra"
}

variable "nodes" {
  type = list(object({
    name            = string
    vm_size         = string
    image_urn       = string
    os_disk_size_gb = number
    custom_data     = string
    data_disks      = list(any)
  }))
}

variable "tags" {
  type    = map(string)
  default = {}
}
