output "provisioned_nodes" {
  value = [
    for i, vm in azurerm_linux_virtual_machine.vms : {
      node_name  = var.nodes[i].name
      vm_id      = vm.id
      private_ip = azurerm_network_interface.nic[i].private_ip_address
    }
  ]
}
