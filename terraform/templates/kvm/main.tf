terraform {
  required_version = ">= 1.5.0"
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "~> 0.7.1"
    }
  }
}

provider "libvirt" {
  uri = var.libvirt_uri
}

resource "libvirt_volume" "os_disks" {
  count  = length(var.nodes)
  name   = "${var.nodes[count.index].name}-os.qcow2"
  pool   = var.storage_pool
  source = var.nodes[count.index].base_image
  format = "qcow2"
}

resource "libvirt_cloudinit_disk" "commoninit" {
  count     = length(var.nodes)
  name      = "${var.nodes[count.index].name}-init.iso"
  user_data = var.nodes[count.index].cloud_init
}

resource "libvirt_domain" "domains" {
  count  = length(var.nodes)
  name   = var.nodes[count.index].name
  memory = var.nodes[count.index].memory_mb
  vcpu   = var.nodes[count.index].vcpu

  cloudinit = libvirt_cloudinit_disk.commoninit[count.index].id

  network_interface {
    network_name   = var.network_name
    wait_for_lease = true
  }

  disk {
    volume_id = libvirt_volume.os_disks[count.index].id
  }

  console {
    type        = "pty"
    target_port = "0"
    target_type = "serial"
  }

  graphics {
    type        = "vnc"
    listen_type = "address"
  }
}
