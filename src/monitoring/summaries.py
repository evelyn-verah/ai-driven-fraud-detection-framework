"""Compatibility facade for deterministic monitoring summaries."""
from .engine import summarize_monitoring, write_monitoring_result

__all__ = ["summarize_monitoring", "write_monitoring_result"]
