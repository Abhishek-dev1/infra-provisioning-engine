# Multi-Cloud & Virtualized Infrastructure Provisioning Engine

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.92+-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite_WAL-003B57.svg)](https://www.sqlite.org/)
[![Terraform](https://img.shields.io/badge/IaC-HashiCorp_Terraform-7B42BC.svg)](https://www.terraform.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An asynchronous provisioning control-plane service engineered to orchestrate hybrid Kubernetes worker nodes and virtual machines across public cloud providers (**AWS**, **Azure**, **GCP**) and on-premises virtualization hypervisors (**VMware vSphere/ESXi**, **KVM/libvirt**).

**Author:** [Abhishek Sharma](https://github.com/Abhishek-dev1) ([@Abhishek-dev1](https://github.com/Abhishek-dev1) • [LinkedIn](https://linkedin.com/in/abhishek-sharma-967622216) • [LeetCode](https://leetcode.com/spidy007) • abhishek300680@gmail.com)

---

## 🌟 Core Architecture & Capabilities

- **Asynchronous Control-Plane Engine**: Multi-stage state machine (`PENDING` → `PREFLIGHT_CHECK` → `PROVISIONING` → `ATTACHING_STORAGE` → `VERIFYING` → `COMPLETED`) managed via concurrent worker threads with non-blocking `202 Accepted` API responses.
- **Multi-Cloud & Hypervisor Drivers**: Unified infrastructure driver abstraction supporting AWS (EC2/EBS/EKS), Azure (VMs/Managed Disks/AKS), GCP (Compute Engine/Persistent Disks/GKE), VMware (vSphere vCenter/ESXi VMDK), and KVM/libvirt (QEMU qcow2 bridges).
- **Automated Pre-Flight Quota & Guardrails**: Evaluates vCPU, RAM, storage, and instance quotas against regional capacity thresholds, verifying cloud API reachability and network CIDR capacity prior to launching infrastructure.
- **Storage Attachment & Synthetic I/O Verification**: Validates block device mounting, filesystem integrity (`ext4`/`xfs`), encryption-at-rest status, and executes real-time read/write latency probes with SHA-256 block checksums.
- **Terraform IaC Orchestration**: Programmatically creates isolated workspaces, binds dynamic HCL variable sets, executes the full Terraform lifecycle (`init` → `plan` → `apply` → `destroy`), and supports offline simulation mode for air-gapped CI/CD environments.
- **Enterprise SQLite Backend (WAL Mode)**: Thread-safe, high-concurrency relational data layer with atomic transactions, schema migrations, foreign keys, and operational audit event logging.
- **Production Observability**: Built-in Prometheus telemetry metrics (`/metrics`), Kubernetes-compatible liveness and readiness probes (`/health/live`, `/health/ready`), and 21 interactive REST endpoints documented via OpenAPI/Swagger.

---

## 🏗️ System Architecture

```
                          +-------------------------------------------------------+
                          |      Client Applications / CI/CD Pipelines / CLI      |
                          +-------------------------------------------------------+
                                                     |  HTTP REST / OpenAPI
                                                     v
+-------------------------------------------------------------------------------------------------------+
|                                    FASTAPI CONTROL-PLANE SERVICE                                      |
|                                                                                                       |
|  [ API Layer: /api/v1 ]                                                                               |
|   ├── /provision   ──> Async Job Ingestion, Lifecycle Polling, Infrastructure Teardown                |
|   ├── /preflight   ──> Standalone Capacity & Quota Guardrail Verification                             |
|   ├── /storage     ──> Block & Network Storage Verification & I/O Latency Probes                      |
|   ├── /providers   ──> Multi-Cloud & Hypervisor Health & Quota Utilization Tracking                   |
|   ├── /nodes       ──> Managed Node Inventory & Realtime Telemetry Reporting                          |
|   └── /metrics     ──> Prometheus-Compatible Observability & Health Probes                            |
+-------------------------------------------------------------------------------------------------------+
        |                                       |                                       |
        v                                       v                                       v
+-----------------------+           +-----------------------+           +-------------------------------+
|  PRE-FLIGHT SERVICE   |           |  ORCHESTRATOR WORKER  |           |      STORAGE SUBSYSTEM        |
|                       |           |                       |           |                               |
| • vCPU / RAM Ceilings |           | State Machine:        |           | • Block Device Detection      |
| • Storage Quota Guard | <-------> | PENDING               | <-------> | • POSIX Mount Validation      |
| • Subnet CIDR Sizing  |           |  -> PREFLIGHT_CHECK   |           | • Filesystem Integrity (ext4) |
| • Cloud API Reachable |           |  -> PROVISIONING      |           | • Synthetic Read/Write Probes |
| • Atomic Reservations |           |  -> ATTACHING_STORAGE |           | • SHA-256 Checksum Validation |
+-----------------------+           |  -> VERIFYING         |           +-------------------------------+
                                    |  -> COMPLETED         |
                                    +-----------------------+
                                                |
                                                v
+-------------------------------------------------------------------------------------------------------+
|                                  TERRAFORM IaC EXECUTION ENGINE                                       |
|                                                                                                       |
|   ├── Workspace Isolation: runs/{job_id}/ (terraform.tfvars.json, main.tf, terraform.tfstate)          |
|   └── Execution Wrapper: init -> plan -> apply -> output -> destroy (Live Binary or Simulated Mode)  |
+-------------------------------------------------------------------------------------------------------+
        |                     |                     |                     |                     |
        v                     v                     v                     v                     v
   +----------+          +----------+          +----------+          +----------+          +----------+
   |   AWS    |          |  Azure   |          |   GCP    |          |  VMware  |          |   KVM    |
   | EC2/EKS  |          | VMs/AKS  |          | GCE/GKE  |          | vSphere  |          | libvirt  |
   | gp3 EBS  |          | Managed  |          |    PD    |          |   VMDK   |          |  qcow2   |
   +----------+          +----------+          +----------+          +----------+          +----------+
        \                     \                     \                     /                     /
         \_____________________\_____________________\___________________/_____________________/
                                                |
                                                v
                               +---------------------------------+
                               |   SQLITE HIGH-CONCURRENCY DB    |
                               |                                 |
                               | • provisioning_jobs             |
                               | • nodes & cluster inventory     |
                               | • storage_volumes               |
                               | • provider_quotas               |
                               | • audit_events (tamper-evident) |
                               +---------------------------------+
```

---

## 🚀 Quickstart & Installation

### Prerequisites
- Python 3.11+
- SQLite3
- Optional: HashiCorp Terraform CLI (v1.5.0+)

### 1. Clone & Set Up Virtual Environment
```bash
git clone https://github.com/Abhishek-dev1/infra-provisioning-engine.git
cd infra-provisioning-engine

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
```

### 3. Run Test Suite (100% Passing)
```bash
python3 -m unittest discover -s tests -v
```

### 4. Run Live End-to-End Demo
```bash
python3 scripts/demo_provision.py
```

### 5. Launch Control-Plane REST API
```bash
python3 scripts/run_server.py
```
Open **http://localhost:8000/docs** in your browser for interactive Swagger API documentation.

---

## 📡 REST API Reference

### 1. Provisioning Jobs

#### Submit Provisioning Job
`POST /api/v1/provision` (Returns `202 Accepted`)
```json
{
  "job_name": "prod-k8s-hybrid-pool",
  "provider": "aws",
  "region_or_datacenter": "us-east-1",
  "target_type": "k8s_node",
  "nodes": [
    {
      "name": "aws-worker-01",
      "vcpu": 4,
      "ram_gb": 16,
      "disk_gb": 80,
      "os_distro": "ubuntu-22.04",
      "node_type": "k8s_worker",
      "cluster_id": "hybrid-k8s-prod",
      "k8s_master_endpoint": "10.0.0.10:6443",
      "k8s_join_token": "abcdef.0123456789abcdef",
      "storage_volumes": [
        {
          "name": "fast-data-ebs",
          "volume_type": "aws_ebs",
          "size_gb": 100,
          "mount_point": "/mnt/k8s-data",
          "device_name": "/dev/nvme1n1",
          "iops": 3000,
          "filesystem": "ext4"
        }
      ]
    }
  ],
  "environment": "production",
  "preflight_check": true,
  "verify_storage": true
}
```

#### Poll Job Status & Telemetry
`GET /api/v1/provision/{job_id}`
```json
{
  "id": "job-d7e37a82ca",
  "name": "prod-k8s-hybrid-pool",
  "provider": "aws",
  "target_type": "k8s_node",
  "status": "COMPLETED",
  "nodes_count": 1,
  "preflight_passed": true,
  "nodes": [
    {
      "id": "node-4f1a2b",
      "name": "aws-worker-01",
      "provider": "aws",
      "node_type": "k8s_worker",
      "ip_address": "54.210.10.20",
      "private_ip": "10.0.10.15",
      "status": "HEALTHY",
      "cpu_cores": 4,
      "ram_gb": 16,
      "disk_gb": 80,
      "os_distro": "ubuntu-22.04",
      "health_status": "HEALTHY",
      "health_metrics": {
        "cpu_usage_pct": 8.4,
        "ram_usage_pct": 22.1,
        "disk_usage_pct": 14.5,
        "k8s_node_ready": true
      }
    }
  ]
}
```

#### Teardown Infrastructure
`DELETE /api/v1/provision/{job_id}`
Releases all reserved provider quotas and destroys cloud/virtualized resources.

---

### 2. Standalone Pre-Flight Check
`POST /api/v1/preflight/check`
Validates compute, memory, storage limits, and regional endpoints without provisioning.

### 3. Storage Volume Verification
`POST /api/v1/storage/verify`
Benchmarks I/O read/write latency, verifies POSIX mounting, filesystem health, and data integrity.

### 4. Health & Observability
- `GET /health/live` — Service liveness probe.
- `GET /health/ready` — Database and system readiness probe.
- `GET /metrics` — Prometheus metrics (active jobs, healthy nodes, uptime).
- `GET /api/v1/audit` — Operational audit trail with tamper-evident event logs.

---

## 🐳 Docker & Container Deployment

### Build and Run with Docker
```bash
docker build -t infra-provisioning-engine .
docker run -p 8000:8000 infra-provisioning-engine
```

### Run with Docker Compose
```bash
docker-compose up -d
```

---

## 🛡️ Key Technical Capabilities

1. **Multi-Distribution Linux Support**: Automatically generates validated cloud-init configurations for **Ubuntu 22.04 LTS**, **Red Hat Enterprise Linux 9**, **Debian 12**, and **Rocky Linux 9**.
2. **Crash Resilience & Thread-Safety**: SQLite WAL (Write-Ahead Logging) mode with `PRAGMA foreign_keys = ON` and explicit transaction isolation ensures zero database corruption under high concurrent loads.
3. **Dual Execution Engine**: Supports live infrastructure execution via HashiCorp Terraform binary as well as deterministic simulation mode for testing and air-gapped CI/CD runners.
4. **Automated Resource Recovery**: Guaranteed quota release upon job cancellation, failure, or teardown preventing cloud cost overruns.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
