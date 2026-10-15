"""Exception hierarchy. Everything the pipeline raises on purpose derives from ChangeOrderError."""

from __future__ import annotations


class ChangeOrderError(Exception):
    """Base class for all expected failures."""


class LoaderError(ChangeOrderError):
    """A document could not be read into text."""


class NoTextLayerError(LoaderError):
    """The document has no extractable text (for example a scanned, image-only PDF)."""


class ExtractorError(ChangeOrderError):
    """An extractor could not produce candidates (bad LLM output, API failure, ...)."""
