variable "gcp_project" { type = string }
variable "gcp_region" { type = string; default = "us-central1" }
variable "gcp_zone" { type = string; default = "us-central1-a" }
variable "environment" { type = string; default = "test" }
variable "job_name" { type = string }
variable "nodes" { type = list(any) }
variable "labels" { type = map(string); default = {} }
