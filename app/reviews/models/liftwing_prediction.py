"""LiftWing prediction model for caching ML model results."""

from __future__ import annotations

from django.db import models

from .wiki import Wiki


class LiftWingPrediction(models.Model):
    """Stores LiftWing model predictions for a specific revision."""

    wiki = models.ForeignKey(Wiki, on_delete=models.CASCADE, related_name="liftwing_predictions")
    revid = models.BigIntegerField(unique=True)
    model_name = models.CharField(max_length=100)
    prediction_data = models.JSONField()  # Stores the full JSON response from LiftWing
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("wiki", "revid", "model_name")
        ordering = ["-fetched_at"]

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.wiki.code}:{self.revid} - {self.model_name}"
