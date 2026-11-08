output "provisioned_nodes" {
  value = [
    for i, vm in vsphere_virtual_machine.vm : {
      node_name  = var.nodes[i].name
      vm_moref   = vm.id
      ip_address = vm.default_ip_address
    }
  ]
}
