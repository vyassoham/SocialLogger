"""
Analytics Utility Tests

Verifies aggregation metrics calculations, platform comparisons,
mock analytics populator, and CSV/JSON reports exports.
"""

import os
import pytest
from datetime import date, datetime
from database.manager import DatabaseManager
from database.models import Post, AnalyticsSnapshot
from utils.analytics import AnalyticsCompiler


def test_analytics_aggregation(db: DatabaseManager):
    compiler = AnalyticsCompiler(db)
    
    # 1. Create a published post
    post = db.save_post(Post(
        content="Published post",
        platforms=["twitter"],
        status="published",
        schedule_time=datetime.utcnow()
    ))
    
    # 2. Add snapshots
    today = date.today()
    db.save_analytics_snapshot(AnalyticsSnapshot(
        post_id=post.id,
        snapshot_date=today,
        likes=10,
        shares=2,
        comments=1,
        clicks=5,
        impressions=100
    ))
    db.save_analytics_snapshot(AnalyticsSnapshot(
        post_id=post.id,
        snapshot_date=today + date.resolution,
        likes=15,
        shares=3,
        comments=2,
        clicks=8,
        impressions=150
    ))
    
    # 3. Test compilation
    rep = compiler.compile_post_report(post)
    assert rep["likes"] == 25
    assert rep["shares"] == 5
    assert rep["comments"] == 3
    assert rep["clicks"] == 13
    assert rep["impressions"] == 250
    assert rep["engagements"] == 46
    assert rep["engagement_rate"] == 18.4  # (46 / 250) * 100
    
    # 4. Test platform comparison
    comp = compiler.get_platform_comparison()
    assert comp["twitter"]["impressions"] == 250
    assert comp["twitter"]["engagements"] == 46
    assert comp["twitter"]["posts"] == 1


def test_analytics_dataframe_compilation(db: DatabaseManager):
    compiler = AnalyticsCompiler(db)
    
    post = db.save_post(Post(
        content="Sample post",
        platforms=["twitter"],
        status="published",
        schedule_time=datetime.utcnow()
    ))
    
    db.save_analytics_snapshot(AnalyticsSnapshot(
        post_id=post.id,
        snapshot_date=date.today(),
        likes=5,
        shares=1,
        impressions=50
    ))
    
    df = compiler.get_historical_dataframe()
    assert len(df) == 1
    assert "Likes" in df.columns
    assert "Engagements" in df.columns
    assert df.loc[0, "Likes"] == 5
    assert df.loc[0, "Engagements"] == 6


def test_mock_analytics_populator(db: DatabaseManager):
    compiler = AnalyticsCompiler(db)
    
    post = db.save_post(Post(
        content="Testing populator",
        platforms=["twitter"],
        status="published",
        schedule_time=datetime.utcnow()
    ))
    
    compiler.populate_mock_analytics(post.id, date.today(), days=5)
    
    snaps = db.list_analytics_for_post(post.id)
    assert len(snaps) == 5
    # Verify growing trends
    assert snaps[-1].likes > snaps[0].likes
    assert snaps[-1].impressions > snaps[0].impressions


def test_analytics_reports_exporters(db: DatabaseManager):
    compiler = AnalyticsCompiler(db)
    
    post = db.save_post(Post(
        content="Testing exporters",
        platforms=["twitter"],
        status="published",
        schedule_time=datetime.utcnow()
    ))
    compiler.populate_mock_analytics(post.id, date.today(), days=3)
    
    # Test CSV Export
    csv_file = "test_report.csv"
    compiler.export_posts_summary_csv(csv_file)
    assert os.path.exists(csv_file)
    
    # Read and verify content
    with open(csv_file, "r") as f:
        content = f.read()
        assert "Testing exporters" in content
        assert "twitter" in content
    
    # Test JSON Export
    json_file = "test_report.json"
    compiler.export_posts_summary_json(json_file)
    assert os.path.exists(json_file)
    
    with open(json_file, "r") as f:
        content = f.read()
        assert "Testing exporters" in content
        
    # Clean up test output files
    if os.path.exists(csv_file):
        os.remove(csv_file)
    if os.path.exists(json_file):
        os.remove(json_file)
