"""Platform-specific extraction providers."""

from services.link_capture.extraction.providers.instagram import (
    InstagramOpenGraphExtractor,
)

__all__ = ["InstagramOpenGraphExtractor"]
