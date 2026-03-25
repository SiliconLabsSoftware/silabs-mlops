__version__ = "0.1.0"

# Submodules `data` and `model` are imported lazily via `from sml.ops import data` /
# `from sml.ops import model` so the CLI (`python -m sml.ops.cli`) does not pull
# TensorFlow / ZeroBus / profiler until those subsystems are used.

__all__ = ["__version__"]

