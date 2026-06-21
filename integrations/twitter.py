"""
Twitter/X Platform Adapter

Simulates Twitter API behaviors, validating strict character length limits (280 characters)
and tracking remaining API call quotas.
"""

import uuid
import random
import hashlib
from typing import Optional, Dict, Tuple, Any
from datetime import datetime, timedelta

from .base import BasePlatformAdapter


class TwitterAdapter(BasePlatformAdapter):
    """Mock Twitter/X API Adapter."""

    def __init__(self, handle: str, credentials: Dict[str, Any]):
        super().__init__(handle, credentials)
        self.char_limit = 280
        # Initialize mock rate limit states in credentials if not existing
        if "rate_limit_remaining" not in self.credentials:
            self.credentials["rate_limit_remaining"] = 15
            self.credentials["rate_limit_reset"] = (datetime.utcnow() + timedelta(minutes=15)).isoformat()

    def publish(self, content: str, media_url: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        # Check rate limits
        remaining, reset_time = self.get_rate_limits()
        if remaining <= 0:
            if datetime.utcnow() < reset_time:
                return False, "Rate limit exceeded (HTTP 429). Reset at " + reset_time.isoformat(), None
            else:
                # Reset rate limit
                self.credentials["rate_limit_remaining"] = 15
                self.credentials["rate_limit_reset"] = (datetime.utcnow() + timedelta(minutes=15)).isoformat()

        # Decrement rate limit
        self.credentials["rate_limit_remaining"] -= 1

        # Validate Twitter content length
        if len(content) > self.char_limit:
            return False, f"Twitter post content exceeds {self.char_limit} characters (got {len(content)})", None

        # Simulate publishing success
        tweet_id = f"tw_{uuid.uuid4().hex[:16]}"
        tweet_url = f"https://twitter.com/{self.handle.lstrip('@')}/status/{tweet_id}"
        return True, tweet_id, tweet_url

    def fetch_metrics(self, external_id: str) -> Dict[str, int]:
        """Generates deterministic mock metrics based on hashing the post ID."""
        h = int(hashlib.md5(external_id.encode("utf-8")).hexdigest(), 16)
        
        # Base seed metrics
        base_views = 100 + (h % 900)
        likes = int(base_views * 0.08)
        shares = int(base_views * 0.02)
        comments = int(base_views * 0.01)
        clicks = int(base_views * 0.05)
        
        # Add some random growth over time
        random.seed(h)
        likes += random.randint(10, 50)
        shares += random.randint(2, 15)
        comments += random.randint(1, 10)
        clicks += random.randint(5, 25)
        impressions = base_views + likes * 5 + shares * 10
        
        return {
            "likes": likes,
            "shares": shares,
            "comments": comments,
            "clicks": clicks,
            "impressions": impressions
        }

    def check_connection(self) -> str:
        # Check mock credentials integrity
        token = self.credentials.get("access_token", "")
        if not token:
            return "reauth_required"
        if token.startswith("expired_"):
            return "reauth_required"
        if token.startswith("suspended_"):
            return "suspended"
        return "active"

    def get_rate_limits(self) -> Tuple[int, datetime]:
        remaining = self.credentials["rate_limit_remaining"]
        reset_time = datetime.fromisoformat(self.credentials["rate_limit_reset"])
        return remaining, reset_time
