terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Key Pair for Node Access
resource "aws_key_pair" "node_key" {
  key_name   = "${var.job_name}-key"
  public_key = var.ssh_public_key
}

# Provision EC2 Nodes / Hybrid K8s Workers
resource "aws_instance" "nodes" {
  count                  = length(var.nodes)
  ami                    = var.nodes[count.index].ami
  instance_type          = var.nodes[count.index].instance_type
  key_name               = aws_key_pair.node_key.key_name
  user_data              = var.nodes[count.index].user_data

  root_block_device {
    volume_size           = var.nodes[count.index].root_disk_size
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  tags = merge(
    var.tags,
    {
      Name        = var.nodes[count.index].name
      Role        = "kubernetes-worker"
      Provisioner = "MultiCloudProvisioner"
    }
  )
}

# Attach EBS Volumes to Worker Nodes
resource "aws_ebs_volume" "extra_volumes" {
  count             = length(local.flattened_volumes)
  availability_zone = aws_instance.nodes[local.flattened_volumes[count.index].node_index].availability_zone
  size              = local.flattened_volumes[count.index].volume_size
  type              = local.flattened_volumes[count.index].volume_type
  iops              = local.flattened_volumes[count.index].iops
  encrypted         = true

  tags = {
    Name = local.flattened_volumes[count.index].device_name
  }
}

resource "aws_volume_attachment" "ebs_att" {
  count       = length(local.flattened_volumes)
  device_name = local.flattened_volumes[count.index].device_name
  volume_id   = aws_ebs_volume.extra_volumes[count.index].id
  instance_id = aws_instance.nodes[local.flattened_volumes[count.index].node_index].id
}

locals {
  flattened_volumes = flatten([
    for n_idx, n in var.nodes : [
      for v in n.volumes : merge(v, { node_index = n_idx })
    ]
  ])
}
