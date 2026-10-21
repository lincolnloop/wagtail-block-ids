"""Block walk and labels, moved here from wagtail-inspect's ``test_block_map.py``.

- blocks_for_field yields stream children with correct uuid/type/label/parent
- blocks_for_field yields list children under their stream-child parent
- blocks_for_field recurses into StructBlock fields to find nested lists
"""

import pytest
from wagtail.blocks import CharBlock, ListBlock, StructBlock
from wagtail.fields import StreamField as _StreamField

from tests.block_map_fakes import (
    _FakeListValue,
    _FakePage,
    _FakeStreamField,
    _FakeStreamValue,
    _FakeStructValue,
    _ListChild,
    _make_uuid,
    _StreamChild,
)
from wagtail_block_ids.blocks import (
    _label_from_class_name,
    _parent_label_from_list_block,
    _singularize_name,
    blocks_for_field,
    resolve_block_type,
)


@pytest.fixture(autouse=True)
def _patch_isinstance_for_fake_streamfield(monkeypatch):
    """Make _FakeStreamField pass isinstance(field, StreamField)."""
    import builtins

    _original = builtins.isinstance

    def _patched(obj, types):
        if types is _StreamField and type(obj) is _FakeStreamField:
            return True
        return _original(obj, types)

    monkeypatch.setattr(builtins, "isinstance", _patched)


@pytest.fixture(autouse=True)
def _patch_fake_page_meta(monkeypatch):
    """Route _meta.get_fields() on _FakePage instances."""

    class _Meta:
        def __init__(self, page):
            self._page = page

        def get_fields(self):
            return self._page._meta_get_fields()

    original_init = _FakePage.__init__

    def new_init(self, sv):
        original_init(self, sv)
        self._meta = _Meta(self)

    monkeypatch.setattr(_FakePage, "__init__", new_init)


# ---------------------------------------------------------------------------
# blocks_for_field
# ---------------------------------------------------------------------------


def test_blocks_for_field_yields_stream_child():
    uid = _make_uuid()
    sv = _FakeStreamValue([_StreamChild(uid, "hero", "Hero", "plain text")])

    entries = list(blocks_for_field(sv))

    assert len(entries) == 1
    assert entries[0] == (uid, "hero", "Hero", None)


def test_blocks_for_field_yields_list_children_under_stream_parent():
    parent_id = _make_uuid()
    child_id_1 = _make_uuid()
    child_id_2 = _make_uuid()

    list_value = _FakeListValue(
        [
            _ListChild(child_id_1, "logo", "Logo", "img1"),
            _ListChild(child_id_2, "logo", "Logo", "img2"),
        ]
    )
    sv = _FakeStreamValue([_StreamChild(parent_id, "logo_cloud", "Logo Cloud", list_value)])

    entries = list(blocks_for_field(sv))
    ids = [e[0] for e in entries]

    assert parent_id in ids
    assert child_id_1 in ids
    assert child_id_2 in ids
    # children must report parent_id as their parent
    child_entries = [e for e in entries if e[0] in (child_id_1, child_id_2)]
    for entry in child_entries:
        assert entry[3] == parent_id


def test_blocks_for_field_recurses_into_struct_value():
    parent_id = _make_uuid()
    child_id = _make_uuid()

    list_value = _FakeListValue([_ListChild(child_id, "item", "Item", "val")])
    struct_value = _FakeStructValue({"items": list_value})
    sv = _FakeStreamValue([_StreamChild(parent_id, "section", "Section", struct_value)])

    entries = list(blocks_for_field(sv))
    ids = [e[0] for e in entries]

    assert parent_id in ids
    assert child_id in ids


# ---------------------------------------------------------------------------
# flat_block_map_for_instance
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Label resolution for list children
# ---------------------------------------------------------------------------


class FeatureItemBlock(StructBlock):
    title = CharBlock()


class StatItemBlock(StructBlock):
    value_field = CharBlock()

    class Meta:
        label = "Stat"


def test_list_child_label_falls_back_to_class_name():
    """When label and name are empty, derive from the class name."""
    parent_id = _make_uuid()

    list_block = ListBlock(FeatureItemBlock())
    list_value = list_block.to_python([{"title": "Hello"}])

    sv = _FakeStreamValue([_StreamChild(parent_id, "grid", "Grid", list_value)])
    entries = list(blocks_for_field(sv))

    child_entries = [e for e in entries if e[3] == parent_id]
    assert len(child_entries) == 1
    assert child_entries[0][2] == "Feature Item"


def test_list_child_type_uses_label_slug_when_name_empty():
    """block_type should be a slug derived from the label."""
    parent_id = _make_uuid()

    block_cls = StatItemBlock
    list_block = ListBlock(block_cls())
    list_value = list_block.to_python([{"value_field": "99%"}])

    sv = _FakeStreamValue([_StreamChild(parent_id, "stats", "Stats", list_value)])
    entries = list(blocks_for_field(sv))

    child_entries = [e for e in entries if e[3] == parent_id]
    assert len(child_entries) == 1
    assert child_entries[0][1] == "stat"  # type: slug of "Stat"
    assert child_entries[0][2] == "Stat"  # label: from Meta.label


# ---------------------------------------------------------------------------
# Helpers: singularize, list parent label, resolve_block_type, class label
# ---------------------------------------------------------------------------


def test_singularize_name_strips_trailing_s():
    assert _singularize_name("values") == "value"
    assert _singularize_name("buttons") == "button"


def test_singularize_name_leaves_faq_and_empty():
    assert _singularize_name("faq") == "faq"
    assert _singularize_name("") == ""


def test_parent_label_from_list_block():
    lb = ListBlock(CharBlock())
    lb.set_name("faq_items")
    lv = lb.to_python(["a"])
    assert _parent_label_from_list_block(lv.list_block) == "Faq item"


def test_parent_label_from_list_block_empty_name():
    lb = ListBlock(CharBlock())
    assert _parent_label_from_list_block(lb) == ""


def test_resolve_block_type_prefers_holder_block_type():
    holder = type(
        "H",
        (),
        {
            "block_type": "from_stream",
            "block": type("B", (), {"name": "ignored", "label": "L"})(),
        },
    )()
    assert resolve_block_type(holder) == "from_stream"


def test_resolve_block_type_uses_block_name_when_no_block_type():
    holder = type(
        "H",
        (),
        {
            "block_type": None,
            "block": type("B", (), {"name": "cta_row", "label": ""})(),
        },
    )()
    assert resolve_block_type(holder) == "cta_row"


def test_resolve_block_type_parent_label_fallback():
    class _WagtailLikeBlock:
        __module__ = "wagtail.blocks"
        name = ""
        label = ""

    holder = type("H", (), {"block_type": None, "block": _WagtailLikeBlock()})()
    assert resolve_block_type(holder, parent_label="Logo") == "logo"


def test_label_from_class_name_wagtail_stock_block():
    assert _label_from_class_name(CharBlock()) == "Item"


def test_label_from_class_name_custom_block_class():
    class PromoTileBlock(StructBlock):
        title = CharBlock()

    assert _label_from_class_name(PromoTileBlock()) == "Promo Tile"


def test_blocks_for_field_nested_struct_list_wires_parent_id():
    """Stream → nested struct dicts → list yields list rows parented to the stream child."""
    outer_id = _make_uuid()
    item_id = _make_uuid()
    list_value = _FakeListValue([_ListChild(item_id, "item", "Item", "hi")])
    struct_inner = _FakeStructValue({"items": list_value})
    struct_outer = _FakeStructValue({"section": struct_inner})
    sv = _FakeStreamValue([_StreamChild(outer_id, "outer", "Outer", struct_outer)])

    entries = list(blocks_for_field(sv))
    item_entries = [e for e in entries if e[0] == item_id]
    assert len(item_entries) == 1
    assert item_entries[0][3] == outer_id
