"""
Database Models & Schemas

Defines SQL schemas for SQLite table generation and Pydantic models for data validation,
ensuring strict types, data constraints, and type safety across the SMM SaaS application.
"""

from datetime import datetime, date
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator


# =====================================================================
# SQL Schema Definitions
# =====================================================================

CREATE_SOCIAL_ACCOUNTS_TABLE = """
CREATE TABLE IF NOT EXISTS social_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    credentials TEXT NOT NULL,          -- JSON string storing encrypted/mock tokens
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'reauth_required', 'suspended'
    rate_limit_remaining INTEGER NOT NULL DEFAULT 100,
    rate_limit_reset TEXT NOT NULL,      -- ISO datetime string
    connected_at TEXT NOT NULL,         -- ISO datetime string
    UNIQUE(platform, handle)
);
"""

CREATE_POSTS_TABLE = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    media_url TEXT,
    platforms TEXT NOT NULL,            -- Comma-separated platform names, e.g., 'twitter,linkedin'
    status TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'scheduled', 'published', 'failed'
    schedule_time TEXT NOT NULL,        -- ISO datetime string
    published_time TEXT,                -- ISO datetime string or NULL
    external_ids TEXT NOT NULL,         -- JSON string mapping platform name -> post_id
    error_message TEXT,                 -- Detailed failure message if status is 'failed'
    created_at TEXT NOT NULL            -- ISO datetime string
);
"""

CREATE_AUDIT_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,               -- e.g., 'POST_PUBLISHED', 'AI_GENERATED', 'ACCOUNT_CONNECTED'
    severity TEXT NOT NULL,             -- 'info', 'warning', 'error'
    timestamp TEXT NOT NULL,            -- ISO datetime string
    details TEXT NOT NULL,
    metadata TEXT NOT NULL              -- JSON string for arbitrary key-values
);
"""

CREATE_ANALYTICS_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    snapshot_date TEXT NOT NULL,        -- YYYY-MM-DD
    likes INTEGER NOT NULL DEFAULT 0,
    shares INTEGER NOT NULL DEFAULT 0,
    comments INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    impressions INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
    UNIQUE(post_id, snapshot_date)
);
"""


# =====================================================================
# Pydantic Schemas
# =====================================================================

class SocialAccount(BaseModel):
    """Pydantic model representing a connected social media account."""
    id: Optional[int] = Field(None, description="Auto-incremented primary key")
    platform: str = Field(..., description="Platform identifier (twitter, linkedin, instagram)")
    handle: str = Field(..., description="User handle / profile name, e.g., '@vyassoham'")
    credentials: Dict[str, Any] = Field(default_factory=dict, description="OAuth or access token details")
    status: str = Field("active", description="Account connection status")
    rate_limit_remaining: int = Field(100, ge=0, description="Available API calls before limit")
    rate_limit_reset: datetime = Field(default_factory=datetime.utcnow, description="Time when rate limits reset")
    connected_at: datetime = Field(default_factory=datetime.utcnow, description="Time when account was linked")

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        valid_platforms = {"twitter", "linkedin", "instagram"}
        val = v.lower().strip()
        if val not in valid_platforms:
            raise ValueError(f"Unsupported platform: {v}. Must be one of {valid_platforms}")
        return val

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = {"active", "reauth_required", "suspended"}
        val = v.lower().strip()
        if val not in valid_statuses:
            raise ValueError(f"Invalid status: {v}. Must be one of {valid_statuses}")
        return val


class Post(BaseModel):
    """Pydantic model representing a social media post/campaign item."""
    id: Optional[int] = Field(None, description="Auto-incremented primary key")
    content: str = Field(..., description="Main post text / body content")
    media_url: Optional[str] = Field(None, description="Optional link to attached media asset")
    platforms: List[str] = Field(..., min_items=1, description="Platforms to publish this post on")
    status: str = Field("draft", description="Post cycle status")
    schedule_time: datetime = Field(..., description="Target scheduled publication time")
    published_time: Optional[datetime] = Field(None, description="Actual publication timestamp")
    external_ids: Dict[str, str] = Field(default_factory=dict, description="Mapped platform -> post ID from publisher")
    error_message: Optional[str] = Field(None, description="Detailed publishing error log")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Post generation timestamp")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Post content cannot be empty")
        return v.strip()

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = {"draft", "scheduled", "published", "failed"}
        val = v.lower().strip()
        if val not in valid_statuses:
            raise ValueError(f"Invalid status: {v}. Must be one of {valid_statuses}")
        return val

    @field_validator("platforms")
    @classmethod
    def validate_platforms_list(cls, v: List[str]) -> List[str]:
        valid_platforms = {"twitter", "linkedin", "instagram"}
        cleaned = []
        for p in v:
            val = p.lower().strip()
            if val not in valid_platforms:
                raise ValueError(f"Unsupported platform in list: {p}")
            cleaned.append(val)
        return cleaned


class AuditLog(BaseModel):
    """Pydantic model representing a system-level audit trail entry."""
    id: Optional[int] = Field(None, description="Auto-incremented primary key")
    action: str = Field(..., description="Audit action category")
    severity: str = Field("info", description="Log level: info, warning, error")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Audit log timestamp")
    details: str = Field(..., description="Human-readable description of what occurred")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Contextual parameters")

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        valid_levels = {"info", "warning", "error"}
        val = v.lower().strip()
        if val not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return val


class AnalyticsSnapshot(BaseModel):
    """Pydantic model representing daily metrics recorded for a published post."""
    id: Optional[int] = Field(None, description="Auto-incremented primary key")
    post_id: int = Field(..., description="Associated published post ID")
    snapshot_date: date = Field(..., description="Calendar date of this snapshot")
    likes: int = Field(0, ge=0, description="Cumulative likes")
    shares: int = Field(0, ge=0, description="Cumulative shares / retweets")
    comments: int = Field(0, ge=0, description="Cumulative comments / replies")
    clicks: int = Field(0, ge=0, description="Cumulative link clicks")
    impressions: int = Field(0, ge=0, description="Cumulative reach / impressions")

    @property
    def total_engagements(self) -> int:
        """Helper to compute sum of all physical interactions."""
        return self.likes + self.shares + self.comments + self.clicks

    @property
    def engagement_rate(self) -> float:
        """Helper to compute engagement rate percentage."""
        if self.impressions == 0:
            return 0.0
        return (self.total_engagements / self.impressions) * 100.0
