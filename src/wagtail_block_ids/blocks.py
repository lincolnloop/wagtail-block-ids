"""Walk StreamField values: every stream and list child, with its id, type slug and label.

Moved here from wagtail-inspect (``block_map``), which re-exports these names.
"""

import re
from typing import NamedTuple

from django.utils.text import capfirst
from wagtail.blocks import StreamValue
from wagtail.blocks.list_block import ListValue
from wagtail.fields import StreamField


def _label_from_class_name(block):
    """Label from class name for user blocks; wagtail.* classes → ``Item``."""
    cls = type(block)
    if (cls.__module__ or "").startswith("wagtail."):
        return "Item"
    name = cls.__name__
    if name.endswith("Block"):
        name = name[: -len("Block")]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name) or "Item"


def _singularize_name(name):
    """Strip trailing ``s`` for list field names (naive)."""
    if name and name.endswith("s"):
        return name[:-1]
    return name


def _parent_label_from_list_block(list_block):
    """Singular list child label from the ListBlock's ``name``."""
    name = getattr(list_block, "name", "") or ""
    if not name:
        return ""
    singular = _singularize_name(name)
    return capfirst(singular.replace("_", " "))


def resolve_block_type(block_holder, parent_label=""):
    """Type slug for StreamChild / ListChild / BoundBlock-like holders."""
    block = getattr(block_holder, "block", None)
    block_type = getattr(block_holder, "block_type", None)

    if not block_type and block:
        label = block.name or block.label or _label_from_class_name(block)
        if label != "Item":
            block_type = label

    if not block_type:
        block_type = parent_label or "item"

    return block_type.lower().replace(" ", "_")


def resolve_block_label(block_holder, parent_label=""):
    """Human label for block holders; falls back to *parent_label* or ``Item``."""
    block = getattr(block_holder, "block", None)
    if block:
        label = block.label or _label_from_class_name(block)
        if label != "Item":
            return label
    return parent_label or "Item"


class BlockInfo(NamedTuple):
    """A stream or list child as the walk yields it and the marks write it."""

    id: str | None
    type: str
    label: str
    parent_id: str | None = None


def describe(child, *, list_block=None, parent_id=None):
    """``BlockInfo`` for a stream or list child; list children need their *list_block*."""
    parent_label = _parent_label_from_list_block(list_block) if list_block else ""
    return BlockInfo(
        getattr(child, "id", None),
        resolve_block_type(child, parent_label),
        resolve_block_label(child, parent_label),
        parent_id,
    )


def blocks_for_field(stream_value, parent_id=None):
    """Yield a ``BlockInfo`` for every stream and list child, in page order."""
    for child in stream_value:
        yield describe(child, parent_id=parent_id)
        yield from _recurse_value(child.value, parent_id=child.id)


def _recurse_value(value, parent_id=None):
    if isinstance(value, StreamValue):
        yield from blocks_for_field(value, parent_id=parent_id)
    elif isinstance(value, ListValue):
        for child in value.bound_blocks:
            if isinstance(child, str):
                continue
            yield describe(child, list_block=value.list_block, parent_id=parent_id)
            yield from _recurse_value(child.value, parent_id=child.id)
    elif isinstance(value, dict):
        for field_value in value.values():
            yield from _recurse_value(field_value, parent_id=parent_id)


def stream_values(page):
    """``(field name, StreamValue)`` for every non-empty StreamField on *page*'s model."""
    model = getattr(page, "specific_class", None) or type(page)
    for field in model._meta.get_fields():
        if not isinstance(field, StreamField):
            continue
        value = getattr(page, field.name, None)
        if isinstance(value, StreamValue):
            yield field.name, value


def block_ids(page):
    """UUIDs of every stream and list child on *page*, top-level and nested, in page order."""
    return [str(info.id) for _name, value in stream_values(page) for info in blocks_for_field(value) if info.id]
