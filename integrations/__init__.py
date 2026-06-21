"""
Platform Adapters Package

Exposes a factory function to retrieve platform adapters dynamically.
"""

from typing import Dict, Any, Type
from .base import BasePlatformAdapter
from .twitter import TwitterAdapter
from .linkedin import LinkedInAdapter
from .instagram import InstagramAdapter

ADAPTER_MAPPING: Dict[str, Type[BasePlatformAdapter]] = {
    "twitter": TwitterAdapter,
    "linkedin": LinkedInAdapter,
    "instagram": InstagramAdapter
}


def get_adapter(platform: str, handle: str, credentials: Dict[str, Any]) -> BasePlatformAdapter:
    """
    Factory function to retrieve a configured platform adapter.

    Args:
        platform: Platform name ('twitter', 'linkedin', 'instagram')
        handle: Account username handle
        credentials: User access keys dictionary

    Returns:
        Configured BasePlatformAdapter instance
    """
    platform_key = platform.lower().strip()
    if platform_key not in ADAPTER_MAPPING:
        raise ValueError(f"Unsupported platform mapping: '{platform}'")
    return ADAPTER_MAPPING[platform_key](handle, credentials)
