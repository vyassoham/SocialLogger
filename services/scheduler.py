"""
Post Scheduler & Publisher Module

Provides queue processing, multi-platform publication management,
resilient retry logic, and detailed system auditing for publishing schedules.
"""

from datetime import datetime, timedelta
import logging
from typing import List, Optional

from database.manager import DatabaseManager
from database.models import Post, SocialAccount
from integrations import get_adapter


class PostScheduler:
    """SMM Post Scheduler managing post queues and publishing pipelines."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.logger = logging.getLogger("SocialLogger.Scheduler")

    def process_pending_queue(self) -> int:
        """
        Polls the database for scheduled posts that are due, publishes them,
        and logs outcomes.
        
        Returns:
            Number of posts processed.
        """
        pending_posts = self.db.get_pending_posts()
        if not pending_posts:
            return 0

        self.db.log_event(
            action="QUEUE_POLL",
            severity="info",
            details=f"Found {len(pending_posts)} pending posts to process.",
            metadata={"count": len(pending_posts)}
        )

        processed_count = 0
        for post in pending_posts:
            self._publish_post(post)
            processed_count += 1

        return processed_count

    def _publish_post(self, post: Post):
        """Processes a single post across all of its remaining targeted platforms."""
        # Find remaining platforms that haven't been successfully published to
        target_platforms = post.platforms
        successful_publish = post.external_ids or {}
        
        platforms_to_publish = [p for p in target_platforms if p not in successful_publish]
        
        if not platforms_to_publish:
            # Already completed publishing, mark as published
            post.status = "published"
            post.published_time = datetime.utcnow()
            self.db.save_post(post)
            return

        failures = {}
        for platform in platforms_to_publish:
            # 1. Fetch active account for this platform
            accounts = self.db.list_social_accounts()
            platform_accounts = [a for a in accounts if a.platform == platform and a.status == "active"]
            
            if not platform_accounts:
                failures[platform] = f"No active social account connected for platform: '{platform}'"
                continue
                
            account = platform_accounts[0]  # Choose first active account
            
            # 2. Build adapter
            try:
                adapter = get_adapter(platform, account.handle, account.credentials)
            except Exception as e:
                failures[platform] = f"Failed to instantiate platform adapter: {e}"
                continue

            # 3. Check credentials status
            conn_status = adapter.check_connection()
            if conn_status != "active":
                account.status = conn_status
                self.db.save_social_account(account)
                self.db.log_event(
                    action="ACCOUNT_ALERT",
                    severity="warning",
                    details=f"Account {account.handle} on {platform} changed status to: {conn_status}",
                    metadata={"account_id": account.id, "status": conn_status}
                )
                failures[platform] = f"Connected account is not active (Status: '{conn_status}')"
                continue

            # 4. Attempt to publish
            success, result_id_or_err, post_url = adapter.publish(post.content, post.media_url)
            
            # Sync rate limits back to database
            rem_calls, reset_t = adapter.get_rate_limits()
            self.db.update_rate_limits(account.id, rem_calls, reset_t)
            
            if success:
                successful_publish[platform] = result_id_or_err
                self.db.log_event(
                    action="POST_PUBLISHED",
                    severity="info",
                    details=f"Successfully published post to {platform} ({account.handle}). URL: {post_url}",
                    metadata={"post_id": post.id, "platform": platform, "external_id": result_id_or_err, "url": post_url}
                )
            else:
                failures[platform] = result_id_or_err
                self.db.log_event(
                    action="PUBLISH_ATTEMPT_FAILED",
                    severity="error",
                    details=f"Failed to publish post to {platform}: {result_id_or_err}",
                    metadata={"post_id": post.id, "platform": platform, "error": result_id_or_err}
                )

        # 5. Update post status based on outcomes
        post.external_ids = successful_publish
        
        # Check if all targeted platforms are now satisfied
        all_completed = all(p in successful_publish for p in target_platforms)
        
        if all_completed:
            post.status = "published"
            post.published_time = datetime.utcnow()
            post.error_message = None
            self.db.log_event(
                action="CAMPAIGN_SUCCESS",
                severity="info",
                details=f"Post campaign completed successfully across all platforms: {', '.join(target_platforms)}",
                metadata={"post_id": post.id, "platforms": target_platforms}
            )
        else:
            # Some platforms failed
            # If we made partial progress, we keep status as 'scheduled' so it retries,
            # unless all remaining platforms failed with hard errors.
            rate_limit_hits = any("Rate limit" in err for err in failures.values())
            
            if rate_limit_hits:
                post.status = "scheduled" # Retry queue later
                # Push schedule_time forward slightly for back-off
                post.schedule_time = datetime.utcnow() + timedelta(minutes=5)
                post.error_message = f"Rate limited on some platforms. Retrying. Errors: {failures}"
                self.db.log_event(
                    action="PUBLISH_RETRY_SCHEDULED",
                    severity="warning",
                    details=f"Post publication deferred due to rate limits. Retrying in 5 mins.",
                    metadata={"post_id": post.id, "failures": failures}
                )
            else:
                # All remaining channels failed with static errors (e.g. character limits or missing image)
                post.status = "failed"
                post.error_message = f"Publishing failed. Platform errors: {failures}"
                self.db.log_event(
                    action="CAMPAIGN_FAILED",
                    severity="error",
                    details=f"Post campaign failed. Errors: {failures}",
                    metadata={"post_id": post.id, "failures": failures}
                )

        # Save state changes
        self.db.save_post(post)
