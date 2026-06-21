"""
Analytics & Metrics Utilities Module

Calculates key performance metrics (CTR, engagement rates), generates simulated post
performance data for visual mock reporting, and manages data exports to CSV/JSON format.
"""

import csv
import json
from datetime import date, timedelta
from typing import List, Dict, Any, Tuple
import pandas as pd

from database.manager import DatabaseManager
from database.models import AnalyticsSnapshot, Post


class AnalyticsCompiler:
    """Compiles and formats metric snapshots for analytical dashboards and file exports."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def compile_post_report(self, post: Post) -> Dict[str, Any]:
        """Compiles detailed analytics metrics for a single published post."""
        snapshots = self.db.list_analytics_for_post(post.id)
        if not snapshots:
            return {
                "post_id": post.id,
                "likes": 0,
                "shares": 0,
                "comments": 0,
                "clicks": 0,
                "impressions": 0,
                "engagements": 0,
                "engagement_rate": 0.0
            }

        # Sum metrics
        total_likes = sum(s.likes for s in snapshots)
        total_shares = sum(s.shares for s in snapshots)
        total_comments = sum(s.comments for s in snapshots)
        total_clicks = sum(s.clicks for s in snapshots)
        total_impressions = sum(s.impressions for s in snapshots)
        total_engagements = total_likes + total_shares + total_comments + total_clicks

        rate = (total_engagements / total_impressions * 100.0) if total_impressions > 0 else 0.0

        return {
            "post_id": post.id,
            "likes": total_likes,
            "shares": total_shares,
            "comments": total_comments,
            "clicks": total_clicks,
            "impressions": total_impressions,
            "engagements": total_engagements,
            "engagement_rate": round(rate, 2)
        }

    def get_platform_comparison(self) -> Dict[str, Dict[str, int]]:
        """Aggregates impressions and engagements grouped by social platform."""
        posts = self.db.list_posts(status="published")
        comparison = {
            "twitter": {"impressions": 0, "engagements": 0, "posts": 0},
            "linkedin": {"impressions": 0, "engagements": 0, "posts": 0},
            "instagram": {"impressions": 0, "engagements": 0, "posts": 0}
        }

        for post in posts:
            report = self.compile_post_report(post)
            # Since a post can target multiple platforms, distribute the metrics equally
            n_platforms = len(post.platforms)
            if n_platforms == 0:
                continue
            
            share_impressions = int(report["impressions"] / n_platforms)
            share_engagements = int(report["engagements"] / n_platforms)

            for platform in post.platforms:
                plat = platform.lower().strip()
                if plat in comparison:
                    comparison[plat]["impressions"] += share_impressions
                    comparison[plat]["engagements"] += share_engagements
                    comparison[plat]["posts"] += 1

        return comparison

    def get_historical_dataframe(self) -> pd.DataFrame:
        """Compiles daily historical metric snapshot aggregations into a Pandas DataFrame."""
        daily_data = self.db.get_aggregated_daily_metrics()
        if not daily_data:
            return pd.DataFrame(columns=["Date", "Likes", "Shares", "Comments", "Clicks", "Impressions", "Engagements"])

        rows = []
        for d in daily_data:
            engagements = d["likes"] + d["shares"] + d["comments"] + d["clicks"]
            rows.append({
                "Date": pd.to_datetime(d["date"]),
                "Likes": d["likes"],
                "Shares": d["shares"],
                "Comments": d["comments"],
                "Clicks": d["clicks"],
                "Impressions": d["impressions"],
                "Engagements": engagements
            })

        return pd.DataFrame(rows)

    def populate_mock_analytics(self, post_id: int, publish_date: date, days: int = 7):
        """
        Generates simulated time-series metrics for a newly published post
        to populate the analytics dashboard charts realistically.
        """
        import hashlib
        h = int(hashlib.md5(str(post_id).encode()).hexdigest(), 16)
        
        # Base daily coefficients
        base_likes = 5 + (h % 15)
        base_shares = 1 + (h % 5)
        base_comments = 2 + (h % 8)
        base_clicks = 8 + (h % 20)
        base_impressions = 100 + (h % 400)

        for day in range(days):
            target_date = publish_date + timedelta(days=day)
            
            # Growth curve coefficient (compound growth)
            mult = 1.0 + (day * 0.3) + ((h % 5) * 0.05)
            
            snapshot = AnalyticsSnapshot(
                post_id=post_id,
                snapshot_date=target_date,
                likes=int(base_likes * mult),
                shares=int(base_shares * mult),
                comments=int(base_comments * mult),
                clicks=int(base_clicks * mult),
                impressions=int(base_impressions * mult)
            )
            self.db.save_analytics_snapshot(snapshot)

    # =====================================================================
    # File Exporters
    # =====================================================================

    def export_posts_summary_csv(self, filepath: str) -> str:
        """Exports a summary of all posts and metrics to a CSV file."""
        posts = self.db.list_posts()
        
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Post ID", "Content", "Platforms", "Status", "Scheduled Time", 
                "Published Time", "Likes", "Shares", "Comments", "Clicks", "Impressions"
            ])
            
            for post in posts:
                metrics = self.compile_post_report(post) if post.status == "published" else {}
                writer.writerow([
                    post.id,
                    post.content,
                    ",".join(post.platforms),
                    post.status,
                    post.schedule_time.isoformat(),
                    post.published_time.isoformat() if post.published_time else "N/A",
                    metrics.get("likes", 0),
                    metrics.get("shares", 0),
                    metrics.get("comments", 0),
                    metrics.get("clicks", 0),
                    metrics.get("impressions", 0),
                ])
        return filepath

    def export_posts_summary_json(self, filepath: str) -> str:
        """Exports a summary of all posts and metrics to a JSON file."""
        posts = self.db.list_posts()
        data = []
        
        for post in posts:
            metrics = self.compile_post_report(post) if post.status == "published" else {
                "likes": 0, "shares": 0, "comments": 0, "clicks": 0, "impressions": 0, "engagement_rate": 0.0
            }
            data.append({
                "id": post.id,
                "content": post.content,
                "platforms": post.platforms,
                "status": post.status,
                "schedule_time": post.schedule_time.isoformat(),
                "published_time": post.published_time.isoformat() if post.published_time else None,
                "metrics": metrics,
                "created_at": post.created_at.isoformat()
            })

        with open(filepath, mode="w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return filepath
