variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "Target AWS Region"
}

variable "job_name" {
  type        = string
  description = "Provisioning Job ID or Blueprint Name"
}

variable "environment" {
  type        = string
  default     = "test"
  description = "Target Deployment Environment"
}

variable "ssh_public_key" {
  type        = string
  default     = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG5vZGUtcHJvdmlzaW9uZXIta2V5 abhishek@infra"
  description = "Public SSH key injected into instance metadata"
}

variable "nodes" {
  type = list(object({
    name           = string
    instance_type  = string
    ami            = string
    root_disk_size = number
    user_data      = string
    volumes        = list(any)
  }))
  description = "Specifications for target compute nodes"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Metadata tags"
}
