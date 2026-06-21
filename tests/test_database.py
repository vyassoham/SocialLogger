"""
Database CRUD Tests

Verifies SQLite table integrity, CRUD database operations,
foreign key cascades, and Pydantic model constraint checking.
"""

import pytest
from datetime import datetime, timedelta, date
from database.models import SocialAccount, Post, AuditLog, AnalyticsSnapshot
from database.manager import DatabaseManager


def test_social_account_crud(db: DatabaseManager):
    # 1. Create and Save Account
    account = SocialAccount(
        platform="twitter",
        handle="@test_user",
        credentials={"access_token": "token123"},
        status="active"
    )
    saved = db.save_social_account(account)
    assert saved.id is not None
    
    # 2. Get Account
    fetched = db.get_social_account(saved.id)
    assert fetched is not None
    assert fetched.platform == "twitter"
    assert fetched.handle == "@test_user"
    assert fetched.credentials == {"access_token": "token123"}
    assert fetched.status == "active"
    
    # 3. Get Account by Handle
    fetched_handle = db.get_social_account_by_handle("twitter", "@test_user")
    assert fetched_handle is not None
    assert fetched_handle.id == saved.id
    
    # 4. List Accounts
    accounts = db.list_social_accounts()
    assert len(accounts) == 1
    assert accounts[0].id == saved.id
    
    # 5. Update Account Rate Limits
    reset_time = datetime.utcnow() + timedelta(minutes=10)
    db.update_rate_limits(saved.id, 80, reset_time)
    fetched_updated = db.get_social_account(saved.id)
    assert fetched_updated.rate_limit_remaining == 80
    
    # 6. Delete Account
    deleted = db.delete_social_account(saved.id)
    assert deleted is True
    assert db.get_social_account(saved.id) is None


def test_post_crud(db: DatabaseManager):
    # 1. Create and Save Post
    post = Post(
        content="Testing post database integration #Python",
        platforms=["twitter", "linkedin"],
        status="scheduled",
        schedule_time=datetime.utcnow() + timedelta(hours=2)
    )
    saved = db.save_post(post)
    assert saved.id is not None
    
    # 2. Get Post
    fetched = db.get_post(saved.id)
    assert fetched is not None
    assert fetched.content == "Testing post database integration #Python"
    assert fetched.platforms == ["twitter", "linkedin"]
    assert fetched.status == "scheduled"
    
    # 3. List Posts with Filter
    posts_tw = db.list_posts(platform="twitter")
    assert len(posts_tw) == 1
    assert posts_tw[0].id == saved.id
    
    # List Posts with status filter
    posts_sched = db.list_posts(status="scheduled")
    assert len(posts_sched) == 1
    
    posts_pub = db.list_posts(status="published")
    assert len(posts_pub) == 0
    
    # 4. Get Pending Posts
    pending_before = db.get_pending_posts()
    assert len(pending_before) == 0  # scheduled in future
    
    saved.schedule_time = datetime.utcnow() - timedelta(minutes=5)
    db.save_post(saved)
    pending_after = db.get_pending_posts()
    assert len(pending_after) == 1
    assert pending_after[0].id == saved.id
    
    # 5. Delete Post
    deleted = db.delete_post(saved.id)
    assert deleted is True
    assert db.get_post(saved.id) is None


def test_audit_logs(db: DatabaseManager):
    db.log_event("TEST_ACTION", "Testing audit logs details", "info", {"meta_key": "meta_val"})
    db.log_event("WARNING_ACTION", "Warning details", "warning")
    
    logs = db.list_audit_logs()
    assert len(logs) == 2
    assert logs[0].action == "WARNING_ACTION"
    assert logs[0].severity == "warning"
    assert logs[1].action == "TEST_ACTION"
    assert logs[1].severity == "info"
    assert logs[1].metadata == {"meta_key": "meta_val"}


def test_analytics_snapshots(db: DatabaseManager):
    # Create Post first
    post = db.save_post(Post(
        content="Published Post",
        platforms=["twitter"],
        status="published",
        schedule_time=datetime.utcnow()
    ))
    
    # Save snap
    snap = AnalyticsSnapshot(
        post_id=post.id,
        snapshot_date=date.today(),
        likes=50,
        shares=10,
        comments=5,
        clicks=25,
        impressions=1000
    )
    saved_snap = db.save_analytics_snapshot(snap)
    assert saved_snap.id is not None
    
    # Fetch
    snaps = db.list_analytics_for_post(post.id)
    assert len(snaps) == 1
    assert snaps[0].likes == 50
    assert snaps[0].total_engagements == 90
    assert snaps[0].engagement_rate == 9.0
    
    # Aggregated metrics
    agg = db.get_aggregated_daily_metrics()
    assert len(agg) == 1
    assert agg[0]["likes"] == 50
    assert agg[0]["impressions"] == 1000
    
    # Cascade Delete
    db.delete_post(post.id)
    assert len(db.list_analytics_for_post(post.id)) == 0
