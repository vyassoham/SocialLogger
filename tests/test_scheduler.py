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


def test_scheduler_queue_processing(db: DatabaseManager):
    scheduler = PostScheduler(db)
    
    # 1. Seed active accounts
    db.save_social_account(SocialAccount(
        platform="twitter",
        handle="@soham_tw",
        credentials={"access_token": "token123"}
    ))
    db.save_social_account(SocialAccount(
        platform="linkedin",
        handle="Soham Vyas",
        credentials={"access_token": "token456"}
    ))
    
    # 2. Seed scheduled posts
    # Future post (should NOT be processed)
    future_post = db.save_post(Post(
        content="Future update",
        platforms=["twitter"],
        status="scheduled",
        schedule_time=datetime.utcnow() + timedelta(hours=5)
    ))
    
    # Past post (SHOULD be processed)
    past_post = db.save_post(Post(
        content="Past update to publish",
        platforms=["twitter", "linkedin"],
        status="scheduled",
        schedule_time=datetime.utcnow() - timedelta(minutes=5)
    ))
    
    # 3. Process Queue
    processed = scheduler.process_pending_queue()
    assert processed == 1  # Only the past post
    
    # 4. Assert past post published
    updated_past = db.get_post(past_post.id)
    assert updated_past.status == "published"
    assert updated_past.published_time is not None
    assert "twitter" in updated_past.external_ids
    assert "linkedin" in updated_past.external_ids
    
    # Assert future post remains scheduled
    updated_future = db.get_post(future_post.id)
    assert updated_future.status == "scheduled"
    assert updated_future.published_time is None
    
    # Verify rate limit updates on account
    acc_tw = db.get_social_account_by_handle("twitter", "@soham_tw")
    assert acc_tw.rate_limit_remaining == 14  # Decremented by 1


def test_scheduler_hard_failure(db: DatabaseManager):
    scheduler = PostScheduler(db)
    
    # Connect Twitter account but with suspended token
    db.save_social_account(SocialAccount(
        platform="twitter",
        handle="@soham_tw",
        credentials={"access_token": "suspended_token"}
    ))
    
    # Past post targeting suspended account
    post = db.save_post(Post(
        content="Post targeting suspended account",
        platforms=["twitter"],
        status="scheduled",
        schedule_time=datetime.utcnow() - timedelta(minutes=1)
    ))
    
    # Process
    scheduler.process_pending_queue()
    
    # Should update status to 'failed' and write error details
    updated_post = db.get_post(post.id)
    assert updated_post.status == "failed"
    assert "suspended" in updated_post.error_message


def test_scheduler_rate_limit_retry(db: DatabaseManager):
    scheduler = PostScheduler(db)
    
    # Connect Twitter account with 0 remaining rate limits
    db.save_social_account(SocialAccount(
        platform="twitter",
        handle="@soham_tw",
        credentials={
            "access_token": "token123",
            "rate_limit_remaining": 0,
            "rate_limit_reset": (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        }
    ))
    
    post = db.save_post(Post(
        content="Post during rate limits",
        platforms=["twitter"],
        status="scheduled",
        schedule_time=datetime.utcnow() - timedelta(minutes=1)
    ))
    
    # Process
    scheduler.process_pending_queue()
    
    # Should keep status as 'scheduled', push schedule_time forward for backoff, and log error
    updated_post = db.get_post(post.id)
    assert updated_post.status == "scheduled"
    assert updated_post.schedule_time > datetime.utcnow() + timedelta(minutes=4)
    assert "Rate limit" in updated_post.error_message


def test_scheduler_partial_success(db: DatabaseManager):
    scheduler = PostScheduler(db)
    
    # Twitter: Active
    db.save_social_account(SocialAccount(
        platform="twitter",
        handle="@soham_tw",
        credentials={"access_token": "token123"}
    ))
    # LinkedIn: Suspended (Hard Fail)
    db.save_social_account(SocialAccount(
        platform="linkedin",
        handle="Soham",
        credentials={"access_token": "suspended_token"}
    ))
    
    post = db.save_post(Post(
        content="Testing partial success pipeline",
        platforms=["twitter", "linkedin"],
        status="scheduled",
        schedule_time=datetime.utcnow() - timedelta(minutes=1)
    ))
    
    # Process
    scheduler.process_pending_queue()
    
    # Status should show failed (as one platform failed), but Twitter external ID should be saved!
    updated_post = db.get_post(post.id)
    assert updated_post.status == "failed"
    assert "twitter" in updated_post.external_ids
    assert "linkedin" not in updated_post.external_ids
    
    # Re-enable LinkedIn
    li_acc = db.get_social_account_by_handle("linkedin", "Soham")
    li_acc.credentials["access_token"] = "valid_token"
    li_acc.status = "active"
    db.save_social_account(li_acc)
    
    # Mark post back to scheduled and due
    updated_post.status = "scheduled"
    updated_post.schedule_time = datetime.utcnow() - timedelta(minutes=1)
    db.save_post(updated_post)
    
    # Process again
    scheduler.process_pending_queue()
    
    # Post should now be fully published, having both platform IDs
    final_post = db.get_post(post.id)
    assert final_post.status == "published"
    assert "twitter" in final_post.external_ids
    assert "linkedin" in final_post.external_ids
