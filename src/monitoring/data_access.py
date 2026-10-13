"""Compatibility facade for monitoring input access."""
from .engine import load_frozen_inputs, sha256_file

__all__ = ["load_frozen_inputs", "sha256_file"]
