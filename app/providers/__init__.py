"""
Provider Registry & Factory Module.
Exposes access to all multi-cloud and hypervisor adapters.
"""
from typing import Dict, List, Any, Union
from app.models.schemas import ProviderType
from app.providers.base import BaseProvider
from app.providers.aws_provider import AWSProvider
from app.providers.azure_provider import AzureProvider
from app.providers.gcp_provider import GCPProvider
from app.providers.vmware_provider import VMwareProvider
from app.providers.kvm_provider import KVMProvider

_PROVIDERS: Dict[str, BaseProvider] = {
    "aws": AWSProvider(),
    "azure": AzureProvider(),
    "gcp": GCPProvider(),
    "vmware": VMwareProvider(),
    "kvm": KVMProvider(),
}


def get_provider(provider: Union[ProviderType, str]) -> BaseProvider:
    key = provider.value if isinstance(provider, ProviderType) else str(provider).lower()
    if key not in _PROVIDERS:
        raise ValueError(f"Unsupported infrastructure provider '{key}'. Available: {list(_PROVIDERS.keys())}")
    return _PROVIDERS[key]


def list_supported_providers() -> List[Dict[str, Any]]:
    result = []
    for name, p in _PROVIDERS.items():
        creds = p.validate_credentials()
        result.append(creds)
    return result
