"""
LinkedIn Platform Adapter

Uses the Python `requests` library to send real HTTP requests to the LinkedIn API (v2).
Constructs the required `ugcPosts` JSON payload and authenticates via Bearer Tokens.
"""

import requests
from typing import Optional, Dict, Tuple, Any
from datetime import datetime, timedelta

from .base import BasePlatformAdapter


class LinkedInAdapter(BasePlatformAdapter):
    """Real LinkedIn API Adapter."""

    def __init__(self, handle: str, credentials: Dict[str, Any]):
        super().__init__(handle, credentials)
        self.char_limit = 3000
        
        # Expecting real API credentials
        self.access_token = self.credentials.get("access_token")
        self.person_urn = self.credentials.get("person_urn") # Format: urn:li:person:12345
        
        self.api_url = "https://api.linkedin.com/v2/ugcPosts"

        if "rate_limit_remaining" not in self.credentials:
            self.credentials["rate_limit_remaining"] = 30
            self.credentials["rate_limit_reset"] = (datetime.utcnow() + timedelta(hours=1)).isoformat()

    def publish(self, content: str, media_url: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        if not self.access_token or not self.person_urn:
            return False, "Missing LinkedIn credentials (access_token, person_urn)", None

        # Validate length
        if len(content) > self.char_limit:
            return False, f"LinkedIn post exceeds length limit of {self.char_limit} characters", None

        # Rate Limit tracking
        remaining, reset_time = self.get_rate_limits()
        if remaining <= 0 and datetime.utcnow() < reset_time:
            return False, f"Rate limit exceeded locally. Reset at {reset_time.isoformat()}", None
        
        if remaining <= 0:
            self.credentials["rate_limit_remaining"] = 30
            self.credentials["rate_limit_reset"] = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        self.credentials["rate_limit_remaining"] -= 1

        # Construct official LinkedIn JSON payload
        payload = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": content
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        # If a media_url is provided, LinkedIn requires a complex asset registration first.
        # For simplicity in this general implementation, we attach it as an article link.
        if media_url:
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "ARTICLE"
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                {
                    "status": "READY",
                    "originalUrl": media_url
                }
            ]

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

        try:
            response = requests.post(self.api_url, json=payload, headers=headers)
            
            if response.status_code == 201:
                data = response.json()
                post_id = data.get("id", "unknown_id")
                post_url = f"https://www.linkedin.com/feed/update/{post_id}"
                return True, post_id, post_url
            elif response.status_code == 401:
                return False, f"LinkedIn Unauthorized (HTTP 401): {response.text}", None
            elif response.status_code == 429:
                return False, f"LinkedIn Rate Limit (HTTP 429): {response.text}", None
            else:
                return False, f"LinkedIn API Error ({response.status_code}): {response.text}", None
                
        except requests.RequestException as e:
            return False, f"LinkedIn Network Error: {str(e)}", None

    def fetch_metrics(self, external_id: str) -> Dict[str, int]:
        """Real LinkedIn metrics require the Social Actions API. Returning zeros if inaccessible."""
        if not self.access_token:
            return {"likes": 0, "shares": 0, "comments": 0, "clicks": 0, "impressions": 0}
            
        url = f"https://api.linkedin.com/v2/socialActions/{external_id}"
        headers = {"Authorization": f"Bearer {self.access_token}", "X-Restli-Protocol-Version": "2.0.0"}
        
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "likes": data.get("likesSummary", {}).get("totalLikes", 0),
                    "shares": 0,
                    "comments": data.get("commentsSummary", {}).get("totalFirstLevelComments", 0),
                    "clicks": 0,
                    "impressions": 0
                }
        except Exception:
            pass
            
        return {"likes": 0, "shares": 0, "comments": 0, "clicks": 0, "impressions": 0}

    def check_connection(self) -> str:
        if not self.access_token:
            return "reauth_required"
        try:
            # Hit me endpoint
            resp = requests.get(
                "https://api.linkedin.com/v2/me", 
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            if resp.status_code == 200:
                return "active"
            elif resp.status_code in (401, 403):
                return "reauth_required"
            return "active" # Unclear error, assume active for now
        except Exception:
            return "reauth_required"

    def get_rate_limits(self) -> Tuple[int, datetime]:
        remaining = self.credentials.get("rate_limit_remaining", 30)
        reset_time_str = self.credentials.get("rate_limit_reset")
        reset_time = datetime.fromisoformat(reset_time_str) if reset_time_str else datetime.utcnow()
        return remaining, reset_time
