output "provisioned_nodes" {
  value = [
    for i, dom in libvirt_domain.domains : {
      node_name = var.nodes[i].name
      domain_id = dom.id
    }
  ]
}
