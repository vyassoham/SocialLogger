"""
Twitter/X Platform Adapter

Uses the official Tweepy SDK to send real HTTP requests to the Twitter API v2.
Validates credentials, publishes tweets via OAuth 1.0a User Context, and catches
native API errors like Rate Limits (HTTP 429) or Unauthorized (HTTP 401).
"""

import tweepy
from typing import Optional, Dict, Tuple, Any
from datetime import datetime, timedelta

from .base import BasePlatformAdapter


class TwitterAdapter(BasePlatformAdapter):
    """Real Twitter/X API Adapter via Tweepy."""

    def __init__(self, handle: str, credentials: Dict[str, Any]):
        super().__init__(handle, credentials)
        self.char_limit = 280
        
        # Expecting real API credentials
        self.api_key = self.credentials.get("api_key")
        self.api_secret = self.credentials.get("api_secret")
        self.access_token = self.credentials.get("access_token")
        self.access_secret = self.credentials.get("access_secret")
        
        self.client = None
        if all([self.api_key, self.api_secret, self.access_token, self.access_secret]):
            self.client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_secret
            )

        # Basic local fallback for rate limit tracking
        if "rate_limit_remaining" not in self.credentials:
            self.credentials["rate_limit_remaining"] = 15
            self.credentials["rate_limit_reset"] = (datetime.utcnow() + timedelta(minutes=15)).isoformat()

    def publish(self, content: str, media_url: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        if not self.client:
            return False, "Missing Twitter credentials (api_key, api_secret, access_token, access_secret)", None

        # Enforce hard length limit
        if len(content) > self.char_limit:
            return False, f"Twitter post content exceeds {self.char_limit} characters", None

        # Decrement local rate limit tracking
        remaining, reset_time = self.get_rate_limits()
        if remaining <= 0 and datetime.utcnow() < reset_time:
            return False, f"Rate limit exceeded locally. Reset at {reset_time.isoformat()}", None
        
        if remaining <= 0:
            self.credentials["rate_limit_remaining"] = 15
            self.credentials["rate_limit_reset"] = (datetime.utcnow() + timedelta(minutes=15)).isoformat()

        self.credentials["rate_limit_remaining"] -= 1

        # Real API Execution
        try:
            # Note: Tweepy v2 create_tweet does not easily support media_url strings directly without a separate media upload endpoint.
            # We are submitting the text only for this basic real integration.
            response = self.client.create_tweet(text=content)
            
            if response.data and 'id' in response.data:
                tweet_id = str(response.data['id'])
                tweet_url = f"https://twitter.com/{self.handle.lstrip('@')}/status/{tweet_id}"
                return True, tweet_id, tweet_url
            else:
                return False, f"Twitter API error: {response.errors}", None
                
        except tweepy.TooManyRequests as e:
            return False, f"Twitter Rate Limit (HTTP 429): {str(e)}", None
        except tweepy.Unauthorized as e:
            return False, f"Twitter Unauthorized (HTTP 401): {str(e)}", None
        except tweepy.Forbidden as e:
            return False, f"Twitter Forbidden (HTTP 403): {str(e)}", None
        except Exception as e:
            return False, f"Twitter Publishing Error: {str(e)}", None

    def fetch_metrics(self, external_id: str) -> Dict[str, int]:
        """
        Fetches real metrics using Tweepy get_tweet.
        Requires elevated Twitter API access for public metrics.
        """
        if not self.client:
            return {"likes": 0, "shares": 0, "comments": 0, "clicks": 0, "impressions": 0}
            
        try:
            response = self.client.get_tweet(id=external_id, tweet_fields=["public_metrics"])
            if response.data and response.data.public_metrics:
                metrics = response.data.public_metrics
                return {
                    "likes": metrics.get("like_count", 0),
                    "shares": metrics.get("retweet_count", 0),
                    "comments": metrics.get("reply_count", 0),
                    "clicks": metrics.get("quote_count", 0), # Closest mapping
                    "impressions": metrics.get("impression_count", 0)
                }
        except Exception:
            pass
            
        # Fallback if API fails or lacks permission
        return {"likes": 0, "shares": 0, "comments": 0, "clicks": 0, "impressions": 0}

    def check_connection(self) -> str:
        if not self.client:
            return "reauth_required"
        try:
            # A simple lightweight call to verify token validity
            self.client.get_me()
            return "active"
        except tweepy.Unauthorized:
            return "reauth_required"
        except tweepy.Forbidden:
            return "suspended"
        except Exception:
            return "reauth_required"

    def get_rate_limits(self) -> Tuple[int, datetime]:
        remaining = self.credentials.get("rate_limit_remaining", 15)
        reset_time_str = self.credentials.get("rate_limit_reset")
        reset_time = datetime.fromisoformat(reset_time_str) if reset_time_str else datetime.utcnow()
        return remaining, reset_time
