"""
Email notification service, built on Composio (NOT SMTP, per requirements).

Uses Composio's current v3 SDK (`pip install composio` — the `composio`
package, not the deprecated `composio_core`/`composio_openai` toolset
classes). Direct, non-agentic tool execution via `composio.tools.execute(...)`
is used since we're not routing this through an LLM — we already know
exactly which tool to call and what to send it.

Requires a Gmail (or other email toolkit) connected account to already
exist in Composio for COMPOSIO_CONNECTED_ACCOUNT_ID / the configured user,
set up once via the Composio dashboard or `composio.connected_accounts.initiate(...)`.
That one-time auth setup is out of scope for this service — see README.
"""

from __future__ import annotations

from dataclasses import dataclass

from composio import Composio

from backend.config.logging_config import get_logger
from backend.config.settings import settings
from backend.database.models import Article

logger = get_logger(__name__)

GMAIL_SEND_EMAIL_TOOL = "GMAIL_SEND_EMAIL"


class NotificationError(Exception):
    """Raised when an alert email fails to send."""


@dataclass
class AlertPayload:
    article: Article
    matched_keywords: list[str]
    matched_categories: list[str]


class ComposioEmailNotifier:
    """Reusable notification service — swap/extend with Slack, Teams, etc. later
    by adding sibling classes with the same `send_alert` contract."""

    def __init__(self) -> None:
        if not settings.composio_api_key:
            raise NotificationError(
                "COMPOSIO_API_KEY is not set. Configure it in your environment/.env."
            )
        self._client = Composio(api_key=settings.composio_api_key)

    def send_alert(self, payload: AlertPayload) -> None:
        if not settings.notification_email_to:
            raise NotificationError("NOTIFICATION_EMAIL_TO is not configured.")

        article = payload.article
        subject = "New Activity Detected"
        body = self._build_body(payload)

        try:
            self._client.tools.execute(
                slug=GMAIL_SEND_EMAIL_TOOL,
                user_id=settings.composio_connected_account_id or "default",
                arguments={
                    "recipient_email": settings.notification_email_to,
                    "subject": subject,
                    "body": body,
                },
            )
        except Exception as exc:  # Composio raises various exception subclasses
            logger.exception(
                "email_send_failed",
                extra={"article_id": article.id, "article_url": article.url},
            )
            raise NotificationError(f"Failed to send alert email: {exc}") from exc

        logger.info(
            "email_sent",
            extra={
                "article_id": article.id,
                "article_url": article.url,
                "matched_keywords": payload.matched_keywords,
            },
        )

    @staticmethod
    def _build_body(payload: AlertPayload) -> str:
        article = payload.article
        keyword_line = ", ".join(payload.matched_keywords) or "N/A"
        category_line = ", ".join(sorted(set(payload.matched_categories))) or "N/A"

        return (
            f"Matched Keywords: {keyword_line}\n"
            f"Matched Category: {category_line}\n\n"
            f"Article Title: {article.title}\n"
            f"Source Website: {article.source}\n"
            f"Date: {article.published_date or 'Unknown'}\n\n"
            f"Summary:\n{article.summary or 'N/A'}\n\n"
            f"Article URL: {article.url}\n"
        )
