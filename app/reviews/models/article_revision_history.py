"""Article revision history model for caching revision data."""

from __future__ import annotations

from django.db import models


class ArticleRevisionHistory(models.Model):
    """Cache for article revision history to avoid redundant API calls."""

    wiki = models.ForeignKey("Wiki", on_delete=models.CASCADE, related_name="article_revisions")
    page_title = models.CharField(max_length=500)
    revision_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("wiki", "page_title")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Revision history for {self.page_title} on {self.wiki.code}"
