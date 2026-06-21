"""
Scheduler Service Tests

Tests the queue polling pipeline, multi-platform publishing logic, rate limit backoffs,
resilience against partial account failures, and audit logging.
"""

import pytest
from datetime import datetime, timedelta
from database.manager import DatabaseManager
from database.models import SocialAccount, Post
from services.scheduler import PostScheduler


def test_scheduler_queue_processing(db: DatabaseManager, mocker):
    # Mock adapters
    mock_tw_adapter = mocker.MagicMock()
    mock_tw_adapter.check_connection.return_value = "active"
    mock_tw_adapter.get_rate_limits.return_value = (15, datetime.utcnow())
    mock_tw_adapter.publish.return_value = (True, "tw_123", "url")
    
    mock_li_adapter = mocker.MagicMock()
    mock_li_adapter.check_connection.return_value = "active"
    mock_li_adapter.get_rate_limits.return_value = (30, datetime.utcnow())
    mock_li_adapter.publish.return_value = (True, "li_123", "url")
    
    def side_effect_get_adapter(platform, handle, creds):
        if platform == "twitter": return mock_tw_adapter
        if platform == "linkedin": return mock_li_adapter
    mocker.patch('services.scheduler.get_adapter', side_effect=side_effect_get_adapter)

    scheduler = PostScheduler(db)
    
    db.save_social_account(SocialAccount(
        platform="twitter", handle="@soham_tw", credentials={}
    ))
    db.save_social_account(SocialAccount(
        platform="linkedin", handle="Soham Vyas", credentials={}
    ))
    
    future_post = db.save_post(Post(
        content="Future update", platforms=["twitter"], status="scheduled",
        schedule_time=datetime.utcnow() + timedelta(hours=5)
    ))
    
    past_post = db.save_post(Post(
        content="Past update to publish", platforms=["twitter", "linkedin"], status="scheduled",
        schedule_time=datetime.utcnow() - timedelta(minutes=5)
    ))
    
    processed = scheduler.process_pending_queue()
    assert processed == 1
    
    updated_past = db.get_post(past_post.id)
    assert updated_past.status == "published"
    assert "twitter" in updated_past.external_ids
    assert "linkedin" in updated_past.external_ids


def test_scheduler_hard_failure(db: DatabaseManager, mocker):
    mock_tw_adapter = mocker.MagicMock()
    mock_tw_adapter.check_connection.return_value = "suspended" # Hard fail
    mocker.patch('services.scheduler.get_adapter', return_value=mock_tw_adapter)

    scheduler = PostScheduler(db)
    db.save_social_account(SocialAccount(platform="twitter", handle="@soham_tw", credentials={}))
    
    post = db.save_post(Post(
        content="Post targeting suspended account", platforms=["twitter"], status="scheduled",
        schedule_time=datetime.utcnow() - timedelta(minutes=1)
    ))
    
    scheduler.process_pending_queue()
    updated_post = db.get_post(post.id)
    assert updated_post.status == "failed"
    assert "not active" in updated_post.error_message


def test_scheduler_rate_limit_retry(db: DatabaseManager, mocker):
    mock_tw_adapter = mocker.MagicMock()
    mock_tw_adapter.check_connection.return_value = "active"
    mock_tw_adapter.get_rate_limits.return_value = (0, datetime.utcnow() + timedelta(minutes=10))
    mock_tw_adapter.publish.return_value = (False, "Rate limit exceeded locally.", None)
    mocker.patch('services.scheduler.get_adapter', return_value=mock_tw_adapter)

    scheduler = PostScheduler(db)
    db.save_social_account(SocialAccount(platform="twitter", handle="@soham_tw", credentials={}))
    
    post = db.save_post(Post(
        content="Post during rate limits", platforms=["twitter"], status="scheduled",
        schedule_time=datetime.utcnow() - timedelta(minutes=1)
    ))
    
    scheduler.process_pending_queue()
    updated_post = db.get_post(post.id)
    assert updated_post.status == "scheduled"
    assert updated_post.schedule_time > datetime.utcnow() + timedelta(minutes=4)
    assert "Rate limit" in updated_post.error_message


def test_scheduler_partial_success(db: DatabaseManager, mocker):
    mock_tw_adapter = mocker.MagicMock()
    mock_tw_adapter.check_connection.return_value = "active"
    mock_tw_adapter.get_rate_limits.return_value = (15, datetime.utcnow())
    mock_tw_adapter.publish.return_value = (True, "tw_123", "url")
    
    mock_li_adapter = mocker.MagicMock()
    mock_li_adapter.check_connection.return_value = "suspended" # LinkedIn fails
    
    def side_effect_get_adapter(platform, handle, creds):
        if platform == "twitter": return mock_tw_adapter
        if platform == "linkedin": return mock_li_adapter
    mocker.patch('services.scheduler.get_adapter', side_effect=side_effect_get_adapter)

    scheduler = PostScheduler(db)
    db.save_social_account(SocialAccount(platform="twitter", handle="@soham_tw", credentials={}))
    db.save_social_account(SocialAccount(platform="linkedin", handle="Soham", credentials={}))
    
    post = db.save_post(Post(
        content="Testing partial success pipeline", platforms=["twitter", "linkedin"],
        status="scheduled", schedule_time=datetime.utcnow() - timedelta(minutes=1)
    ))
    
    scheduler.process_pending_queue()
    updated_post = db.get_post(post.id)
    assert updated_post.status == "failed"
    assert "twitter" in updated_post.external_ids
    assert "linkedin" not in updated_post.external_ids
