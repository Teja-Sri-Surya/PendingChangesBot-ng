"""Article revision history model for caching revision data."""

from __future__ import annotations

from django.db import models

from .pending_page import PendingPage
from .wiki import Wiki


class ArticleRevisionHistory(models.Model):
    """Stores a snapshot of an article's revision history."""

    wiki = models.ForeignKey(Wiki, on_delete=models.CASCADE, related_name="article_revision_histories")
    page = models.ForeignKey(PendingPage, on_delete=models.CASCADE, related_name="revision_histories", null=True, blank=True)
    page_title = models.CharField(max_length=500)
    revid = models.BigIntegerField(unique=True)
    parentid = models.BigIntegerField(null=True, blank=True)
    user_name = models.CharField(max_length=255, blank=True, null=True)
    user_id = models.BigIntegerField(null=True, blank=True)
    timestamp = models.DateTimeField()
    comment = models.TextField(blank=True, null=True)
    size = models.IntegerField(null=True, blank=True)
    sha1 = models.CharField(max_length=40, blank=True, null=True)
    # Store full revision data if needed, e.g., for diffs or other metadata
    full_data = models.JSONField(default=dict, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("wiki", "revid")
        ordering = ["-timestamp"]

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.page_title} (Rev: {self.revid})"
