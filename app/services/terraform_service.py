"""
Terraform IaC Orchestration Service.
Manages isolated Terraform workspaces, variable generation, execution lifecycle (init, plan, apply, destroy),
and output state extraction across AWS, Azure, GCP, VMware, and KVM.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from app.config import settings
from app.models.schemas import ProvisioningRequest
from app.providers import get_provider
from app.repositories.audit_repository import audit_repo


class TerraformService:
    def __init__(self):
        self.runs_base_dir = Path(settings.TERRAFORM_RUN_DIR)
        self.runs_base_dir.mkdir(parents=True, exist_ok=True)
        self.templates_base_dir = Path(settings.TERRAFORM_TEMPLATES_DIR)

    def prepare_workspace(self, job_id: str, request: ProvisioningRequest) -> Path:
        """Create isolated workspace and generate provider HCL + tfvars.json."""
        run_dir = self.runs_base_dir / job_id
        run_dir.mkdir(parents=True, exist_ok=True)

        provider = get_provider(request.provider)
        tfvars = provider.generate_terraform_vars(request, str(run_dir))

        # Write terraform.tfvars.json
        tfvars_path = run_dir / "terraform.tfvars.json"
        with open(tfvars_path, "w", encoding="utf-8") as f:
            json.dump(tfvars, f, indent=2)

        # Copy or generate main.tf, variables.tf, outputs.tf from provider template
        template_dir = self.templates_base_dir / request.provider.value
        if template_dir.exists() and any(template_dir.iterdir()):
            for item in template_dir.glob("*.tf"):
                shutil.copy(item, run_dir / item.name)
        else:
            self._write_fallback_hcl(run_dir, request)

        return run_dir

    def execute_apply(self, job_id: str, request: ProvisioningRequest) -> Dict[str, Any]:
        """Execute Terraform init, plan, and apply for a provisioning job."""
        run_dir = self.prepare_workspace(job_id, request)
        provider = get_provider(request.provider)

        # Check if terraform binary is available and simulation mode is disabled
        tf_bin = shutil.which(settings.TERRAFORM_BIN)
        can_run_cli = (tf_bin is not None) and (not settings.SIMULATE_TERRAFORM)

        if can_run_cli:
            return self._run_terraform_cli(run_dir, job_id)
        else:
            return self._run_simulated_terraform(run_dir, job_id, request, provider)

    def execute_destroy(self, job_id: str, provider_name: str) -> Dict[str, Any]:
        """Execute Terraform destroy to tear down provisioned infrastructure."""
        run_dir = self.runs_base_dir / job_id
        if not run_dir.exists():
            return {"success": True, "message": "Workspace already removed."}

        tf_bin = shutil.which(settings.TERRAFORM_BIN)
        can_run_cli = (tf_bin is not None) and (not settings.SIMULATE_TERRAFORM)

        if can_run_cli:
            res = subprocess.run(
                [settings.TERRAFORM_BIN, "destroy", "-auto-approve", "-no-color"],
                cwd=str(run_dir),
                capture_output=True,
                text=True
            )
            return {
                "success": res.returncode == 0,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        else:
            # Simulated teardown
            return {
                "success": True,
                "simulated": True,
                "message": f"Successfully destroyed infrastructure for job {job_id} across {provider_name}."
            }

    def _run_terraform_cli(self, run_dir: Path, job_id: str) -> Dict[str, Any]:
        """Execute live Terraform binary commands."""
        env = os.environ.copy()
        env["TF_IN_AUTOMATION"] = "1"

        # 1. terraform init
        init_res = subprocess.run(
            [settings.TERRAFORM_BIN, "init", "-no-color"],
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            env=env
        )
        if init_res.returncode != 0:
            return {
                "success": False,
                "stage": "init",
                "error": init_res.stderr or init_res.stdout
            }

        # 2. terraform apply
        apply_res = subprocess.run(
            [settings.TERRAFORM_BIN, "apply", "-auto-approve", "-no-color"],
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            env=env
        )
        if apply_res.returncode != 0:
            return {
                "success": False,
                "stage": "apply",
                "error": apply_res.stderr or apply_res.stdout
            }

        # 3. terraform output -json
        out_res = subprocess.run(
            [settings.TERRAFORM_BIN, "output", "-json"],
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            env=env
        )
        outputs = json.loads(out_res.stdout) if out_res.returncode == 0 else {}

        return {
            "success": True,
            "stage": "completed",
            "outputs": outputs,
            "stdout": apply_res.stdout
        }

    def _run_simulated_terraform(
        self,
        run_dir: Path,
        job_id: str,
        request: ProvisioningRequest,
        provider: Any
    ) -> Dict[str, Any]:
        """Simulate Terraform apply with realistic outputs and write tfstate."""
        provisioned_nodes = []
        for idx, node in enumerate(request.nodes):
            mock_attrs = provider.simulate_node_provision(node, job_id, idx)
            provisioned_nodes.append(mock_attrs)

        tfstate = {
            "version": 4,
            "terraform_version": "1.6.0",
            "serial": 1,
            "lineage": f"lin-{job_id}",
            "outputs": {
                "provisioned_nodes": {"value": provisioned_nodes, "type": "tuple"},
                "total_nodes": {"value": len(provisioned_nodes), "type": "number"},
                "provider": {"value": request.provider.value, "type": "string"},
                "environment": {"value": request.environment, "type": "string"}
            },
            "resources": [
                {
                    "mode": "managed",
                    "type": f"{request.provider.value}_instance",
                    "name": node.name,
                    "instances": [{"attributes": provisioned_nodes[idx]}]
                }
                for idx, node in enumerate(request.nodes)
            ]
        }

        # Write terraform.tfstate to disk
        state_file = run_dir / "terraform.tfstate"
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(tfstate, f, indent=2)

        return {
            "success": True,
            "stage": "completed",
            "simulated": True,
            "outputs": tfstate["outputs"],
            "nodes_data": provisioned_nodes
        }

    def _write_fallback_hcl(self, run_dir: Path, request: ProvisioningRequest) -> None:
        """Write clean, syntactically valid HCL templates if template directory is empty."""
        main_tf = f"""# Terraform HCL Blueprint for {request.provider.value.upper()}
terraform {{
  required_version = ">= 1.5.0"
}}

variable "job_name" {{
  type = string
}}

variable "environment" {{
  type = string
}}

variable "nodes" {{
  type = any
}}

output "cluster_job_id" {{
  value = var.job_name
}}
"""
        with open(run_dir / "main.tf", "w", encoding="utf-8") as f:
            f.write(main_tf)


terraform_service = TerraformService()
