terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project
  region  = var.gcp_region
  zone    = var.gcp_zone
}

resource "google_compute_instance" "instances" {
  count        = length(var.nodes)
  name         = var.nodes[count.index].name
  machine_type = var.nodes[count.index].machine_type
  zone         = var.gcp_zone

  boot_disk {
    initialize_params {
      image = var.nodes[count.index].boot_image
      size  = var.nodes[count.index].boot_disk_size_gb
      type  = "pd-balanced"
    }
  }

  network_interface {
    network = "default"
    access_config {}
  }

  metadata_startup_script = var.nodes[count.index].metadata_startup_script
  labels                  = var.labels
}
