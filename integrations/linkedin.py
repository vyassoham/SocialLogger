"""
LinkedIn Platform Adapter

Simulates LinkedIn API behaviors, supporting longer text shares (up to 3000 characters)
and tracking rate limits.
"""

import uuid
import random
import hashlib
from typing import Optional, Dict, Tuple, Any
from datetime import datetime, timedelta

from .base import BasePlatformAdapter


class LinkedInAdapter(BasePlatformAdapter):
    """Mock LinkedIn API Adapter."""

    def __init__(self, handle: str, credentials: Dict[str, Any]):
        super().__init__(handle, credentials)
        self.char_limit = 3000
        if "rate_limit_remaining" not in self.credentials:
            self.credentials["rate_limit_remaining"] = 30
            self.credentials["rate_limit_reset"] = (datetime.utcnow() + timedelta(hours=1)).isoformat()

    def publish(self, content: str, media_url: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        # Check rate limits
        remaining, reset_time = self.get_rate_limits()
        if remaining <= 0:
            if datetime.utcnow() < reset_time:
                return False, "Rate limit exceeded (HTTP 429). Reset at " + reset_time.isoformat(), None
            else:
                self.credentials["rate_limit_remaining"] = 30
                self.credentials["rate_limit_reset"] = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        # Decrement rate limit
        self.credentials["rate_limit_remaining"] -= 1

        # Validate length
        if len(content) > self.char_limit:
            return False, f"LinkedIn post exceeds length limit of {self.char_limit} characters", None

        # Simulate publishing success
        linkedin_id = f"li_{uuid.uuid4().hex[:16]}"
        post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{linkedin_id}"
        return True, linkedin_id, post_url

    def fetch_metrics(self, external_id: str) -> Dict[str, int]:
        h = int(hashlib.md5(external_id.encode("utf-8")).hexdigest(), 16)
        
        # Base seed metrics
        base_views = 200 + (h % 1800)
        likes = int(base_views * 0.05)   # LinkedIn has lower like ratios but higher impressions
        shares = int(base_views * 0.005)
        comments = int(base_views * 0.02) # Higher comment ratios
        clicks = int(base_views * 0.04)
        
        random.seed(h)
        likes += random.randint(20, 100)
        shares += random.randint(1, 8)
        comments += random.randint(5, 30)
        clicks += random.randint(10, 60)
        impressions = base_views + likes * 8 + comments * 12
        
        return {
            "likes": likes,
            "shares": shares,
            "comments": comments,
            "clicks": clicks,
            "impressions": impressions
        }

    def check_connection(self) -> str:
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
