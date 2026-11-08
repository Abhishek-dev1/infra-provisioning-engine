output "provisioned_nodes" {
  value = [
    for i, inst in aws_instance.nodes : {
      node_name    = var.nodes[i].name
      instance_id  = inst.id
      private_ip   = inst.private_ip
      public_ip    = inst.public_ip
      arn          = inst.arn
    }
  ]
  description = "List of provisioned AWS EC2 instances"
}

output "job_id" {
  value = var.job_name
}
