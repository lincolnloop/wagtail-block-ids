"""Minimal page/stream fakes for ``test_block_map.py``.

``flat_block_map_for_instance`` uses ``isinstance(field, StreamField)`` and
``page._meta.get_fields()``.  We avoid a DB-backed page, but ``_FakeStreamField``
is not a ``StreamField`` subclass, so the test module applies an autouse
``isinstance`` monkeypatch — never reuse that pattern from global ``conftest.py``.
"""

from __future__ import annotations

import uuid

from wagtail.blocks.list_block import ListValue


def _make_uuid() -> str:
    return str(uuid.uuid4())


class _StreamChild:
    def __init__(self, id, block_type, label, value):
        self.id = id
        self.block_type = block_type
        self.block = type("B", (), {"name": block_type, "label": label})()
        self.value = value


class _ListChild:
    def __init__(self, id, block_type, label, value):
        self.id = id
        self.block_type = block_type
        self.block = type("B", (), {"name": block_type, "label": label})()
        self.value = value


class _FakeListValue(ListValue):
    """ListValue subclass whose .bound_blocks returns pre-built _ListChild stubs."""

    def __init__(self, children):
        self._children = children

    @property
    def bound_blocks(self):
        return self._children

    def __iter__(self):
        return iter(self._children)


class _FakeStreamValue:
    """Minimal StreamValue stub that iterates over _StreamChild objects."""

    def __init__(self, children):
        self._children = children

    def __iter__(self):
        return iter(self._children)


class _FakeStructValue(dict):
    """Minimal StructValue stub — just a dict whose .values() are traversed."""


class _FakeStreamField:
    """Pretends to be a StreamField so isinstance check passes."""

    name = "body"


class _FakePage:
    """Minimal page stub with a single StreamField."""

    def __init__(self, stream_value):
        self._stream_value = stream_value
        self.body = stream_value

    def _meta_get_fields(self):
        field = _FakeStreamField()
        return [field]


def make_page_with_stream(*children):
    sv = _FakeStreamValue(list(children))
    return _FakePage(sv)
