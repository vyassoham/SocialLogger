"""
Platform Integration Tests

Verifies adapters' specific validations (Twitter 280 char limit, Instagram media attachment check),
credentials validation checks, and API rate limit decrement logic.
"""

import pytest
from datetime import datetime
from integrations import get_adapter
from integrations.twitter import TwitterAdapter
from integrations.linkedin import LinkedInAdapter
from integrations.instagram import InstagramAdapter


def test_twitter_adapter():
    creds = {"access_token": "token123"}
    adapter = get_adapter("twitter", "@test_tw", creds)
    
    assert isinstance(adapter, TwitterAdapter)
    assert adapter.check_connection() == "active"
    
    # Check rate limit initial state
    rem, _ = adapter.get_rate_limits()
    assert rem == 15
    
    # Test valid publish
    success, id_val, url = adapter.publish("Hello World!")
    assert success is True
    assert id_val.startswith("tw_")
    assert "status" in url
    
    # Verify rate limit decreased
    new_rem, _ = adapter.get_rate_limits()
    assert new_rem == 14
    
    # Test content length validation
    long_content = "x" * 281
    success_long, err, _ = adapter.publish(long_content)
    assert success_long is False
    assert "exceeds 280 characters" in err


def test_linkedin_adapter():
    creds = {"access_token": "token456"}
    adapter = get_adapter("linkedin", "Soham", creds)
    
    assert isinstance(adapter, LinkedInAdapter)
    assert adapter.check_connection() == "active"
    
    success, id_val, url = adapter.publish("LinkedIn post text")
    assert success is True
    assert id_val.startswith("li_")
    
    # Test length check
    long_content = "x" * 3001
    success_long, err, _ = adapter.publish(long_content)
    assert success_long is False
    assert "exceeds length limit" in err


def test_instagram_adapter():
    creds = {"access_token": "token789"}
    adapter = get_adapter("instagram", "soham.ig", creds)
    
    assert isinstance(adapter, InstagramAdapter)
    
    # Test publish WITHOUT media_url (Instagram requires media)
    success_no_media, err, _ = adapter.publish("Instagram post text")
    assert success_no_media is False
    assert "requires an image" in err
    
    # Test publish WITH media_url
    success, id_val, url = adapter.publish("Instagram post text", media_url="https://test.com/img.png")
    assert success is True
    assert id_val.startswith("ig_")
    
    # Test caption length limit
    long_content = "x" * 2201
    success_long, err_long, _ = adapter.publish(long_content, media_url="https://test.com/img.png")
    assert success_long is False
    assert "exceeds length limit" in err_long


def test_adapter_metrics():
    # Verify metrics generation is deterministic and returns expected structure
    adapter = get_adapter("twitter", "@test_user", {"access_token": "tok"})
    metrics = adapter.fetch_metrics("tw_post123")
    
    assert "likes" in metrics
    assert "shares" in metrics
    assert "comments" in metrics
    assert "clicks" in metrics
    assert "impressions" in metrics
    assert metrics["impressions"] >= metrics["likes"]


def test_adapter_connection_states():
    # Test connection statuses based on token values
    tw_suspended = get_adapter("twitter", "@tw", {"access_token": "suspended_token"})
    assert tw_suspended.check_connection() == "suspended"
    
    tw_expired = get_adapter("twitter", "@tw", {"access_token": "expired_token"})
    assert tw_expired.check_connection() == "reauth_required"
    
    tw_missing = get_adapter("twitter", "@tw", {})
    assert tw_missing.check_connection() == "reauth_required"
