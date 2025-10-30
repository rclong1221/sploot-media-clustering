from importlib.metadata import version

__all__ = ["__version__"]

try:
    __version__ = version("sploot-media-clustering")
except Exception:  # pragma: no cover
    __version__ = "0.1.0"
