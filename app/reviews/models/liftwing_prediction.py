"""LiftWing prediction model for caching ML model predictions."""

from __future__ import annotations

from django.db import models


class LiftWingPrediction(models.Model):
    """Cache for LiftWing model predictions to avoid redundant API calls."""

    wiki = models.ForeignKey("Wiki", on_delete=models.CASCADE, related_name="liftwing_predictions")
    revision_id = models.BigIntegerField()
    model_name = models.CharField(max_length=100)
    prediction_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("wiki", "revision_id", "model_name")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"LiftWing {self.model_name} prediction for revision {self.revision_id}"
