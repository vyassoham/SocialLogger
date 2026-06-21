"""
Instagram Platform Adapter

Uses the Python `requests` library to interface with the Facebook Graph API.
Executes the authentic Instagram two-step publishing flow:
1. POST to /{ig_user_id}/media to create a container.
2. POST to /{ig_user_id}/media_publish to publish the container.
"""

import requests
import time
from typing import Optional, Dict, Tuple, Any
from datetime import datetime, timedelta

from .base import BasePlatformAdapter


class InstagramAdapter(BasePlatformAdapter):
    """Real Instagram Graph API Adapter."""

    def __init__(self, handle: str, credentials: Dict[str, Any]):
        super().__init__(handle, credentials)
        self.char_limit = 2200
        
        # Expecting real API credentials
        self.access_token = self.credentials.get("access_token")
        self.ig_user_id = self.credentials.get("ig_user_id")
        
        self.api_base = "https://graph.facebook.com/v18.0"

        if "rate_limit_remaining" not in self.credentials:
            self.credentials["rate_limit_remaining"] = 20
            self.credentials["rate_limit_reset"] = (datetime.utcnow() + timedelta(minutes=30)).isoformat()

    def publish(self, content: str, media_url: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        if not self.access_token or not self.ig_user_id:
            return False, "Missing Instagram credentials (access_token, ig_user_id)", None

        if not media_url:
            return False, "Instagram REST API requires an image or video URL to publish", None

        if len(content) > self.char_limit:
            return False, f"Instagram caption exceeds length limit of {self.char_limit} characters", None

        # Rate limits tracking locally
        remaining, reset_time = self.get_rate_limits()
        if remaining <= 0 and datetime.utcnow() < reset_time:
            return False, f"Rate limit exceeded locally. Reset at {reset_time.isoformat()}", None
        
        if remaining <= 0:
            self.credentials["rate_limit_remaining"] = 20
            self.credentials["rate_limit_reset"] = (datetime.utcnow() + timedelta(minutes=30)).isoformat()

        self.credentials["rate_limit_remaining"] -= 1

        try:
            # Step 1: Create Media Container
            container_url = f"{self.api_base}/{self.ig_user_id}/media"
            container_payload = {
                "image_url": media_url,
                "caption": content,
                "access_token": self.access_token
            }
            
            cont_resp = requests.post(container_url, data=container_payload)
            cont_data = cont_resp.json()
            
            if cont_resp.status_code != 200 or "id" not in cont_data:
                err_msg = cont_data.get("error", {}).get("message", "Unknown error")
                return False, f"Instagram Media Upload Error: {err_msg}", None
                
            creation_id = cont_data["id"]
            
            # Brief pause for Instagram processing (sometimes required for large images/videos)
            time.sleep(2)
            
            # Step 2: Publish Media Container
            publish_url = f"{self.api_base}/{self.ig_user_id}/media_publish"
            publish_payload = {
                "creation_id": creation_id,
                "access_token": self.access_token
            }
            
            pub_resp = requests.post(publish_url, data=publish_payload)
            pub_data = pub_resp.json()
            
            if pub_resp.status_code == 200 and "id" in pub_data:
                post_id = pub_data["id"]
                # Instagram Graph API doesn't return the direct web URL, format a generic one
                post_url = f"https://www.instagram.com/p/{post_id}"
                return True, post_id, post_url
            else:
                err_msg = pub_data.get("error", {}).get("message", "Unknown error")
                return False, f"Instagram Publish Error: {err_msg}", None
                
        except requests.RequestException as e:
            return False, f"Instagram Network Error: {str(e)}", None

    def fetch_metrics(self, external_id: str) -> Dict[str, int]:
        """Fetch media insights via Instagram Graph API."""
        if not self.access_token:
            return {"likes": 0, "shares": 0, "comments": 0, "clicks": 0, "impressions": 0}
            
        url = f"{self.api_base}/{external_id}?fields=like_count,comments_count,insights.metric(impressions)&access_token={self.access_token}"
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                data = resp.json()
                impressions = 0
                insights = data.get("insights", {}).get("data", [])
                if insights:
                    impressions = insights[0].get("values", [{}])[0].get("value", 0)
                    
                return {
                    "likes": data.get("like_count", 0),
                    "shares": 0,
                    "comments": data.get("comments_count", 0),
                    "clicks": 0,
                    "impressions": impressions
                }
        except Exception:
            pass
            
        return {"likes": 0, "shares": 0, "comments": 0, "clicks": 0, "impressions": 0}

    def check_connection(self) -> str:
        if not self.access_token or not self.ig_user_id:
            return "reauth_required"
        try:
            url = f"{self.api_base}/{self.ig_user_id}?access_token={self.access_token}"
            resp = requests.get(url)
            if resp.status_code == 200:
                return "active"
            return "reauth_required"
        except Exception:
            return "reauth_required"

    def get_rate_limits(self) -> Tuple[int, datetime]:
        remaining = self.credentials.get("rate_limit_remaining", 20)
        reset_time_str = self.credentials.get("rate_limit_reset")
        reset_time = datetime.fromisoformat(reset_time_str) if reset_time_str else datetime.utcnow()
        return remaining, reset_time
