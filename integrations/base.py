"""
Abstract Platform Adapter Module

Defines the interface constraints for implementing publishing adapters
across diverse social media networks.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Tuple, Any
from datetime import datetime


class BasePlatformAdapter(ABC):
    """Abstract Base Class defining the contract for all platform adapters."""

    def __init__(self, handle: str, credentials: Dict[str, Any]):
        self.handle = handle
        self.credentials = credentials

    @abstractmethod
    def publish(self, content: str, media_url: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Publishes a post to the platform.

        Args:
            content: Text body of the post.
            media_url: Optional remote URL to attached media.

        Returns:
            Tuple of (success_status, external_id_or_error, post_url_or_none)
        """
        pass

    @abstractmethod
    def fetch_metrics(self, external_id: str) -> Dict[str, int]:
        """
        Fetches the current performance stats for a published post.

        Args:
            external_id: The platform-specific post identifier.

        Returns:
            Dictionary containing metrics keys: likes, shares, comments, clicks, impressions
        """
        pass

    @abstractmethod
    def check_connection(self) -> str:
        """
        Verifies if the platform credentials are still valid.

        Returns:
            Account connection status: 'active', 'reauth_required', or 'suspended'
        """
        pass

    @abstractmethod
    def get_rate_limits(self) -> Tuple[int, datetime]:
        """
        Returns the remaining API quota and reset time.

        Returns:
            Tuple of (remaining_calls, reset_timestamp)
        """
        pass
