output "provisioned_nodes" {
  value = [
    for i, inst in google_compute_instance.instances : {
      node_name  = var.nodes[i].name
      instance_id = inst.id
      private_ip = inst.network_interface[0].network_ip
      public_ip  = inst.network_interface[0].access_config[0].nat_ip
    }
  ]
}
