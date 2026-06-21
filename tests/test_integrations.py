"""
Platform Integration Tests (Real API Mocking)

Verifies adapters' specific validations, credentials validation checks,
and API rate limit decrement logic while mocking out the actual tweepy
and requests network calls to avoid spamming production servers.
"""

import pytest
from datetime import datetime
from integrations import get_adapter
from integrations.twitter import TwitterAdapter
from integrations.linkedin import LinkedInAdapter
from integrations.instagram import InstagramAdapter
import tweepy
import requests


def test_twitter_adapter(mocker):
    # Mock tweepy client
    mock_client = mocker.MagicMock()
    mock_response = mocker.MagicMock()
    mock_response.data = {'id': '123456789'}
    mock_client.create_tweet.return_value = mock_response
    mocker.patch('tweepy.Client', return_value=mock_client)

    creds = {
        "api_key": "k", "api_secret": "s", 
        "access_token": "t", "access_secret": "ts",
        "rate_limit_remaining": 15
    }
    adapter = get_adapter("twitter", "@test_tw", creds)
    
    assert isinstance(adapter, TwitterAdapter)
    
    # Test valid publish
    success, id_val, url = adapter.publish("Hello World!")
    assert success is True
    assert id_val == "123456789"
    assert "status/123456789" in url
    
    # Verify rate limit decreased
    new_rem, _ = adapter.get_rate_limits()
    assert new_rem == 14
    
    # Test content length validation
    long_content = "x" * 281
    success_long, err, _ = adapter.publish(long_content)
    assert success_long is False
    assert "exceeds 280 characters" in err

    # Test missing credentials
    adapter_missing = get_adapter("twitter", "@tw", {"api_key": "123"}) # Missing others
    success_missing, err_miss, _ = adapter_missing.publish("Hi")
    assert success_missing is False
    assert "Missing Twitter credentials" in err_miss


def test_linkedin_adapter(mocker):
    # Mock requests.post
    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": "urn:li:share:123"}
    mocker.patch('requests.post', return_value=mock_resp)

    creds = {"access_token": "token456", "person_urn": "urn:li:person:me"}
    adapter = get_adapter("linkedin", "Soham", creds)
    
    assert isinstance(adapter, LinkedInAdapter)
    
    success, id_val, url = adapter.publish("LinkedIn post text")
    assert success is True
    assert id_val == "urn:li:share:123"
    
    # Test length check
    long_content = "x" * 3001
    success_long, err, _ = adapter.publish(long_content)
    assert success_long is False
    assert "exceeds length limit" in err


def test_instagram_adapter(mocker):
    # Mock requests.post
    # Needs two responses for two steps
    mock_resp_1 = mocker.MagicMock()
    mock_resp_1.status_code = 200
    mock_resp_1.json.return_value = {"id": "container123"}
    
    mock_resp_2 = mocker.MagicMock()
    mock_resp_2.status_code = 200
    mock_resp_2.json.return_value = {"id": "post123"}
    
    mocker.patch('requests.post', side_effect=[mock_resp_1, mock_resp_2])
    mocker.patch('time.sleep', return_value=None) # Speed up test

    creds = {"access_token": "token789", "ig_user_id": "123456"}
    adapter = get_adapter("instagram", "soham.ig", creds)
    
    assert isinstance(adapter, InstagramAdapter)
    
    # Test publish WITHOUT media_url (Instagram requires media)
    success_no_media, err, _ = adapter.publish("Instagram post text")
    assert success_no_media is False
    assert "requires an image" in err
    
    # Test publish WITH media_url
    success, id_val, url = adapter.publish("Instagram post text", media_url="https://test.com/img.png")
    assert success is True
    assert id_val == "post123"
    
    # Test caption length limit
    long_content = "x" * 2201
    success_long, err_long, _ = adapter.publish(long_content, media_url="https://test.com/img.png")
    assert success_long is False
    assert "exceeds length limit" in err_long


def test_adapter_metrics(mocker):
    # Mock Tweepy for metrics
    mock_client = mocker.MagicMock()
    mock_resp = mocker.MagicMock()
    mock_resp.data = mocker.MagicMock()
    mock_resp.data.public_metrics = {"like_count": 50, "impression_count": 500}
    mock_client.get_tweet.return_value = mock_resp
    mocker.patch('tweepy.Client', return_value=mock_client)

    adapter = get_adapter("twitter", "@test_user", {"api_key": "1", "api_secret": "2", "access_token": "3", "access_secret": "4"})
    metrics = adapter.fetch_metrics("tw_post123")
    
    assert metrics["likes"] == 50
    assert metrics["impressions"] == 500
