"""Wagtail Block IDs: mark rendered StreamField blocks so tools can map HTML back to blocks.

Shared by wagtail-inspect and wagtail-live-comments until Wagtail marks blocks itself.
"""

from .blocks import block_ids, blocks_for_field, resolve_block_label, resolve_block_type, stream_values
from .marks import install, is_marking, marking, register_page_marker

__version__ = "0.1.0"

__all__ = [
    "block_ids",
    "blocks_for_field",
    "install",
    "is_marking",
    "marking",
    "register_page_marker",
    "resolve_block_label",
    "resolve_block_type",
    "stream_values",
]
