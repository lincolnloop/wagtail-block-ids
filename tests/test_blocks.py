"""Block walk and labels, on real StreamField values (no database needed).

- blocks_for_field yields stream children with correct uuid/type/label/parent
- blocks_for_field yields list children under their stream-child parent
- blocks_for_field recurses into StructBlock fields to find nested lists
"""

from wagtail.blocks import CharBlock, ListBlock, StreamBlock, StructBlock

from wagtail_block_ids.blocks import (
    BlockInfo,
    _label_from_class_name,
    _parent_label_from_list_block,
    _singularize_name,
    blocks_for_field,
    describe,
    resolve_block_type,
)

PARENT = "11111111-1111-1111-1111-111111111111"
CHILD = "22222222-2222-2222-2222-222222222222"
OTHER = "33333333-3333-3333-3333-333333333333"


def _stream(name, block, value):
    """A one-child StreamValue: *block* named *name*, holding raw *value*."""
    return StreamBlock([(name, block)]).to_python([{"type": name, "id": PARENT, "value": value}])


def _items(*values, ids=(CHILD, OTHER)):
    return [{"type": "item", "id": uid, "value": v} for uid, v in zip(ids, values, strict=False)]


# ---------------------------------------------------------------------------
# blocks_for_field
# ---------------------------------------------------------------------------


def test_blocks_for_field_yields_stream_child():
    sv = _stream("hero", CharBlock(label="Hero"), "plain text")

    assert list(blocks_for_field(sv)) == [BlockInfo(PARENT, "hero", "Hero", None)]


def test_blocks_for_field_yields_list_children_under_stream_parent():
    """List children are named from the list's field name, singularized."""
    sv = _stream("logos", ListBlock(CharBlock()), _items("img1", "img2"))

    assert list(blocks_for_field(sv)) == [
        BlockInfo(PARENT, "logos", "Logos", None),
        BlockInfo(CHILD, "logo", "Logo", PARENT),
        BlockInfo(OTHER, "logo", "Logo", PARENT),
    ]


def test_blocks_for_field_recurses_into_struct_value():
    section = StructBlock([("items", ListBlock(CharBlock()))])
    sv = _stream("section", section, {"items": _items("val")})

    assert list(blocks_for_field(sv))[1] == BlockInfo(CHILD, "item", "Item", PARENT)


def test_blocks_for_field_nested_struct_list_wires_parent_id():
    """Stream → nested struct dicts → list yields list rows parented to the stream child."""
    inner = StructBlock([("items", ListBlock(CharBlock()))])
    outer = StructBlock([("section", inner)])
    sv = _stream("outer", outer, {"section": {"items": _items("hi")}})

    assert [info.parent_id for info in blocks_for_field(sv) if info.id == CHILD] == [PARENT]


def test_blocks_for_field_items_unpack_as_four_tuples():
    """Consumers unpack ``(uuid, type, label, parent_id)``."""
    uid, block_type, label, parent_id = next(blocks_for_field(_stream("hero", CharBlock(), "x")))

    assert (uid, block_type, label, parent_id) == (PARENT, "hero", "Hero", None)


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
    sv = _stream("grid", ListBlock(FeatureItemBlock()), _items({"title": "Hello"}))

    assert list(blocks_for_field(sv))[1].label == "Feature Item"


def test_list_child_type_uses_label_slug_when_name_empty():
    """block_type should be a slug derived from the label."""
    sv = _stream("stats", ListBlock(StatItemBlock()), _items({"value_field": "99%"}))

    assert list(blocks_for_field(sv))[1][1:3] == ("stat", "Stat")


def test_describe_needs_the_list_block_for_list_children():
    list_block = ListBlock(CharBlock())
    list_block.set_name("tags")
    child = list_block.to_python(["news"]).bound_blocks[0]

    assert describe(child, list_block=list_block)[1:3] == ("tag", "Tag")
    assert describe(child)[1:3] == ("item", "Item")


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
    assert _parent_label_from_list_block(lb) == "Faq item"


def test_parent_label_from_list_block_empty_name():
    assert _parent_label_from_list_block(ListBlock(CharBlock())) == ""


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
