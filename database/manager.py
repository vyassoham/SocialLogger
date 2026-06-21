"""
Database Manager Module

Handles database connection pooling, thread-safe transaction execution,
and custom type conversion (de-serializing stored JSON strings and parsing timestamps)
to and from SQLite tables.
"""

import sqlite3
import json
import threading
from datetime import datetime, date
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

from .models import (
    CREATE_SOCIAL_ACCOUNTS_TABLE,
    CREATE_POSTS_TABLE,
    CREATE_AUDIT_LOGS_TABLE,
    CREATE_ANALYTICS_SNAPSHOTS_TABLE,
    SocialAccount,
    Post,
    AuditLog,
    AnalyticsSnapshot
)


class DatabaseManager:
    """Thread-safe SQLite Database Manager utilizing a reentrant lock."""

    def __init__(self, db_path: str = "social_logger.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self.initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign keys support
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def initialize_db(self):
        """Creates the SQLite database and runs all setup scripts if tables do not exist."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(CREATE_SOCIAL_ACCOUNTS_TABLE)
                cursor.execute(CREATE_POSTS_TABLE)
                cursor.execute(CREATE_AUDIT_LOGS_TABLE)
                cursor.execute(CREATE_ANALYTICS_SNAPSHOTS_TABLE)
                conn.commit()

    # =====================================================================
    # Social Accounts CRUD Operations
    # =====================================================================

    def save_social_account(self, account: SocialAccount) -> SocialAccount:
        """Inserts a new social account or updates an existing one."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                creds_json = json.dumps(account.credentials)
                reset_str = account.rate_limit_reset.isoformat()
                connected_str = account.connected_at.isoformat()

                if account.id is None:
                    # Check unique constraint first
                    cursor.execute(
                        "SELECT id FROM social_accounts WHERE platform = ? AND handle = ?",
                        (account.platform, account.handle)
                    )
                    row = cursor.fetchone()
                    if row:
                        # Update instead
                        account.id = row["id"]
                        cursor.execute(
                            """
                            UPDATE social_accounts 
                            SET credentials = ?, status = ?, rate_limit_remaining = ?, 
                                rate_limit_reset = ?
                            WHERE id = ?
                            """,
                            (creds_json, account.status, account.rate_limit_remaining, reset_str, account.id)
                        )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO social_accounts (
                                platform, handle, credentials, status, rate_limit_remaining, 
                                rate_limit_reset, connected_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                account.platform, account.handle, creds_json, account.status,
                                account.rate_limit_remaining, reset_str, connected_str
                            )
                        )
                        account.id = cursor.lastrowid
                else:
                    cursor.execute(
                        """
                        UPDATE social_accounts 
                        SET platform = ?, handle = ?, credentials = ?, status = ?, 
                            rate_limit_remaining = ?, rate_limit_reset = ?, connected_at = ?
                        WHERE id = ?
                        """,
                        (
                            account.platform, account.handle, creds_json, account.status,
                            account.rate_limit_remaining, reset_str, connected_str, account.id
                        )
                    )
                conn.commit()
                return account

    def get_social_account(self, account_id: int) -> Optional[SocialAccount]:
        """Fetch a single social account by its ID."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM social_accounts WHERE id = ?", (account_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_social_account(row)

    def get_social_account_by_handle(self, platform: str, handle: str) -> Optional[SocialAccount]:
        """Fetch a single social account by platform and profile handle."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM social_accounts WHERE platform = ? AND handle = ?",
                    (platform.lower().strip(), handle.strip())
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_social_account(row)

    def list_social_accounts(self) -> List[SocialAccount]:
        """Retrieve all registered social accounts."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM social_accounts ORDER BY platform, handle")
                return [self._row_to_social_account(row) for row in cursor.fetchall()]

    def delete_social_account(self, account_id: int) -> bool:
        """Remove a social account mapping."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM social_accounts WHERE id = ?", (account_id,))
                conn.commit()
                return cursor.rowcount > 0

    def update_rate_limits(self, account_id: int, remaining: int, reset_time: datetime):
        """Quickly updates the rate limits for a given social account."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE social_accounts 
                    SET rate_limit_remaining = ?, rate_limit_reset = ? 
                    WHERE id = ?
                    """,
                    (remaining, reset_time.isoformat(), account_id)
                )
                conn.commit()

    def _row_to_social_account(self, row: sqlite3.Row) -> SocialAccount:
        return SocialAccount(
            id=row["id"],
            platform=row["platform"],
            handle=row["handle"],
            credentials=json.loads(row["credentials"]),
            status=row["status"],
            rate_limit_remaining=row["rate_limit_remaining"],
            rate_limit_reset=datetime.fromisoformat(row["rate_limit_reset"]),
            connected_at=datetime.fromisoformat(row["connected_at"])
        )

    # =====================================================================
    # Posts CRUD Operations
    # =====================================================================

    def save_post(self, post: Post) -> Post:
        """Creates a new post entry or updates an existing scheduled/draft post."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                platforms_str = ",".join(post.platforms)
                sched_str = post.schedule_time.isoformat()
                pub_str = post.published_time.isoformat() if post.published_time else None
                ext_ids_json = json.dumps(post.external_ids)
                created_str = post.created_at.isoformat()

                if post.id is None:
                    cursor.execute(
                        """
                        INSERT INTO posts (
                            content, media_url, platforms, status, schedule_time, 
                            published_time, external_ids, error_message, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            post.content, post.media_url, platforms_str, post.status,
                            sched_str, pub_str, ext_ids_json, post.error_message, created_str
                        )
                    )
                    post.id = cursor.lastrowid
                else:
                    cursor.execute(
                        """
                        UPDATE posts 
                        SET content = ?, media_url = ?, platforms = ?, status = ?, 
                            schedule_time = ?, published_time = ?, external_ids = ?, 
                            error_message = ?, created_at = ?
                        WHERE id = ?
                        """,
                        (
                            post.content, post.media_url, platforms_str, post.status,
                            sched_str, pub_str, ext_ids_json, post.error_message, created_str, post.id
                        )
                    )
                conn.commit()
                return post

    def get_post(self, post_id: int) -> Optional[Post]:
        """Retrieve a single post by ID."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_post(row)

    def list_posts(self, status: Optional[str] = None, platform: Optional[str] = None) -> List[Post]:
        """Fetch posts with optional filtering by status and targeted platform."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM posts"
                params = []
                conditions = []

                if status:
                    conditions.append("status = ?")
                    params.append(status.lower().strip())

                if platform:
                    conditions.append("',' || platforms || ',' LIKE ?")
                    params.append(f"%,{platform.lower().strip()},%")

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += " ORDER BY schedule_time DESC"
                cursor.execute(query, tuple(params))
                return [self._row_to_post(row) for row in cursor.fetchall()]

    def get_pending_posts(self) -> List[Post]:
        """Fetch all 'scheduled' posts that need to be published (schedule_time <= current time)."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now_str = datetime.utcnow().isoformat()
                cursor.execute(
                    "SELECT * FROM posts WHERE status = 'scheduled' AND schedule_time <= ? ORDER BY schedule_time ASC",
                    (now_str,)
                )
                return [self._row_to_post(row) for row in cursor.fetchall()]

    def delete_post(self, post_id: int) -> bool:
        """Deletes a post (and automatically its associated snapshots due to ON DELETE CASCADE)."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))
                conn.commit()
                return cursor.rowcount > 0

    def _row_to_post(self, row: sqlite3.Row) -> Post:
        pub_time = row["published_time"]
        return Post(
            id=row["id"],
            content=row["content"],
            media_url=row["media_url"],
            platforms=row["platforms"].split(",") if row["platforms"] else [],
            status=row["status"],
            schedule_time=datetime.fromisoformat(row["schedule_time"]),
            published_time=datetime.fromisoformat(pub_time) if pub_time else None,
            external_ids=json.loads(row["external_ids"]),
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"])
        )

    # =====================================================================
    # Audit Logs CRUD Operations
    # =====================================================================

    def log_event(self, action: str, details: str, severity: str = "info", metadata: Optional[Dict[str, Any]] = None) -> AuditLog:
        """Saves a new system action event to the audit trail database."""
        with self._lock:
            meta = metadata or {}
            log = AuditLog(action=action, details=details, severity=severity, metadata=meta)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO audit_logs (action, severity, timestamp, details, metadata)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (log.action, log.severity, log.timestamp.isoformat(), log.details, json.dumps(log.metadata))
                )
                log.id = cursor.lastrowid
                conn.commit()
                return log

    def list_audit_logs(self, limit: int = 100) -> List[AuditLog]:
        """Fetch audit records sorted chronologically in descending order."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
                return [
                    AuditLog(
                        id=row["id"],
                        action=row["action"],
                        severity=row["severity"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        details=row["details"],
                        metadata=json.loads(row["metadata"])
                    )
                    for row in cursor.fetchall()
                ]

    # =====================================================================
    # Analytics Snapshots CRUD Operations
    # =====================================================================

    def save_analytics_snapshot(self, snapshot: AnalyticsSnapshot) -> AnalyticsSnapshot:
        """Inserts or overwrites an engagement metrics snapshot for a specific post and date."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                date_str = snapshot.snapshot_date.isoformat()
                cursor.execute(
                    """
                    INSERT INTO analytics_snapshots (
                        post_id, snapshot_date, likes, shares, comments, clicks, impressions
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(post_id, snapshot_date) DO UPDATE SET
                        likes = excluded.likes,
                        shares = excluded.shares,
                        comments = excluded.comments,
                        clicks = excluded.clicks,
                        impressions = excluded.impressions
                    """,
                    (
                        snapshot.post_id, date_str, snapshot.likes, snapshot.shares,
                        snapshot.comments, snapshot.clicks, snapshot.impressions
                    )
                )
                if snapshot.id is None:
                    # Fetch the ID of the newly inserted or updated row
                    cursor.execute(
                        "SELECT id FROM analytics_snapshots WHERE post_id = ? AND snapshot_date = ?",
                        (snapshot.post_id, date_str)
                    )
                    snapshot.id = cursor.fetchone()["id"]
                conn.commit()
                return snapshot

    def list_analytics_for_post(self, post_id: int) -> List[AnalyticsSnapshot]:
        """Fetch chronological analytics snapshots for a specific post."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM analytics_snapshots WHERE post_id = ? ORDER BY snapshot_date ASC",
                    (post_id,)
                )
                return [self._row_to_snapshot(row) for row in cursor.fetchall()]

    def get_aggregated_daily_metrics(self) -> List[Dict[str, Any]]:
        """Aggregates all post metrics by snapshot_date for overview charting."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT 
                        snapshot_date,
                        SUM(likes) as total_likes,
                        SUM(shares) as total_shares,
                        SUM(comments) as total_comments,
                        SUM(clicks) as total_clicks,
                        SUM(impressions) as total_impressions
                    FROM analytics_snapshots
                    GROUP BY snapshot_date
                    ORDER BY snapshot_date ASC
                    """
                )
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "date": date.fromisoformat(row["snapshot_date"]),
                        "likes": row["total_likes"] or 0,
                        "shares": row["total_shares"] or 0,
                        "comments": row["total_comments"] or 0,
                        "clicks": row["total_clicks"] or 0,
                        "impressions": row["total_impressions"] or 0,
                    })
                return results

    def _row_to_snapshot(self, row: sqlite3.Row) -> AnalyticsSnapshot:
        return AnalyticsSnapshot(
            id=row["id"],
            post_id=row["post_id"],
            snapshot_date=date.fromisoformat(row["snapshot_date"]),
            likes=row["likes"],
            shares=row["shares"],
            comments=row["comments"],
            clicks=row["clicks"],
            impressions=row["impressions"]
        )
