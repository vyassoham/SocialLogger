"""
Instagram Platform Adapter

Simulates Instagram API behaviors, requiring media attachments for publishing,
validating caption length (2200 characters limit), and managing rate limits.
"""

import uuid
import random
import hashlib
from typing import Optional, Dict, Tuple, Any
from datetime import datetime, timedelta

from .base import BasePlatformAdapter


class InstagramAdapter(BasePlatformAdapter):
    """Mock Instagram Graph API Adapter."""

    def __init__(self, handle: str, credentials: Dict[str, Any]):
        super().__init__(handle, credentials)
        self.char_limit = 2200
        if "rate_limit_remaining" not in self.credentials:
            self.credentials["rate_limit_remaining"] = 20
            self.credentials["rate_limit_reset"] = (datetime.utcnow() + timedelta(minutes=30)).isoformat()

    def publish(self, content: str, media_url: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        # Check rate limits
        remaining, reset_time = self.get_rate_limits()
        if remaining <= 0:
            if datetime.utcnow() < reset_time:
                return False, "Rate limit exceeded (HTTP 429). Reset at " + reset_time.isoformat(), None
            else:
                self.credentials["rate_limit_remaining"] = 20
                self.credentials["rate_limit_reset"] = (datetime.utcnow() + timedelta(minutes=30)).isoformat()

        # Decrement rate limit
        self.credentials["rate_limit_remaining"] -= 1

        # Instagram CRITICAL requirement: Must have media
        if not media_url:
            return False, "Instagram requires an image or video attachment (media_url)", None

        # Validate caption length
        if len(content) > self.char_limit:
            return False, f"Instagram caption exceeds length limit of {self.char_limit} characters", None

        # Simulate publishing success
        ig_id = f"ig_{uuid.uuid4().hex[:16]}"
        post_url = f"https://www.instagram.com/p/{ig_id}"
        return True, ig_id, post_url

    def fetch_metrics(self, external_id: str) -> Dict[str, int]:
        h = int(hashlib.md5(external_id.encode("utf-8")).hexdigest(), 16)
        
        # Base seed metrics
        base_views = 300 + (h % 3000)
        likes = int(base_views * 0.12)   # Instagram has very high like ratios
        shares = int(base_views * 0.01)   # DMs/shares
        comments = int(base_views * 0.03) # High comments
        clicks = 0                        # Instagram posts don't have clickable body links by default
        
        random.seed(h)
        likes += random.randint(30, 200)
        shares += random.randint(2, 20)
        comments += random.randint(5, 50)
        impressions = base_views + likes * 3 + comments * 5
        
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
