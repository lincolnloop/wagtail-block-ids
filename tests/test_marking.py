"""Marking behaviour, moved here from wagtail-inspect's ``test_patches.py``.

Inside a ``wrap`` scope, output with no root tag or several roots is wrapped in a
``display:contents`` div (inspect's preview behaviour); outside one, only the first
root is marked and nothing is wrapped (live comments' behaviour).
"""

import sys
import threading

from wagtail import blocks
from wagtail.blocks import BoundBlock
from wagtail.blocks.list_block import ListValue

import wagtail_block_ids.marks as patches_module
from wagtail_block_ids.blocks import BlockInfo
from wagtail_block_ids.marks import (
    _ListChildProxy,
    _mark,
    _patched_list_iter,
    _patched_render,
    _Scope,
    install,
    is_marking,
    mark_html,
)


def _open(wrap=True):
    return patches_module._scope.set(_Scope(wrap=wrap))


def _close(token):
    patches_module._scope.reset(token)


# ---------------------------------------------------------------------------
# Minimal stand-ins for BoundBlock subclasses
# ---------------------------------------------------------------------------


class _MockBlock:
    name = "text"
    label = "Text"


class _BoundBlockWithId:
    """Mimics StreamChild / ListChild — has a UUID."""

    id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    block_type = "text"
    block = _MockBlock()


class _BoundBlockWithoutId:
    """Mimics a plain BoundBlock — no UUID, must never be wrapped."""

    id = None
    block = _MockBlock()


# ---------------------------------------------------------------------------
# mark_html
# ---------------------------------------------------------------------------

INFO = BlockInfo("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "text", "Text")


def _wraps(html):
    return 'style="display:contents"' in mark_html(html, INFO, wrap=True)


def test_mark_html_injects_into_root_element():
    """With a root element, the attributes go on it: no wrapper div, even when wrapping is allowed."""
    result = mark_html("<section>hello</section>", INFO, wrap=True)

    assert result == (
        '<section data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" data-block-type="text"'
        ' data-block-label="Text">hello</section>'
    )


def test_mark_html_injects_before_existing_attrs():
    result = mark_html('<div class="hero">content</div>', INFO, wrap=False)

    assert result.startswith('<div data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"')
    assert 'class="hero">content</div>' in result


def test_mark_html_handles_leading_whitespace():
    """Leading whitespace before the first tag is common in Django templates."""
    result = mark_html("\n  <a href='/'>link</a>", INFO, wrap=False)

    assert result.startswith('\n  <a data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"')
    assert "href='/'>link</a>" in result


def test_mark_html_escapes_attribute_values():
    info = BlockInfo("id4", "t", 'Say "hello" & more')

    assert 'data-block-label="Say &quot;hello&quot; &amp; more"' in mark_html("<span>x</span>", info, wrap=False)
    assert 'data-block-label="Say &quot;hello&quot; &amp; more"' in mark_html("x", info, wrap=True)


def test_mark_html_leaves_text_only_output_unmarked_without_wrap():
    assert mark_html("just text", INFO, wrap=False) == "just text"


def test_mark_html_wraps_text_only_output():
    """Plain text has no element to mark, so it gets the display:contents wrapper."""
    assert mark_html("hello", INFO, wrap=True) == (
        '<div data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" data-block-type="text"'
        ' data-block-label="Text" style="display:contents">hello</div>'
    )


def test_mark_html_wraps_multi_root_fragment_whole():
    """Markdown-style siblings are wrapped together, not marked on the first <p> only."""
    result = mark_html("<p>first</p><p>second</p>", INFO, wrap=True)

    assert result.startswith('<div data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"')
    assert result.endswith('style="display:contents"><p>first</p><p>second</p></div>')


def test_mark_html_marks_only_the_first_root_without_wrap():
    result = mark_html("<p>first</p><p>second</p>", INFO, wrap=False)

    assert result.startswith('<p data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"')
    assert result.count("data-block-id") == 1


def test_mark_html_leading_comment_single_root_still_injects():
    """A leading HTML comment does not force multi-root wrapping."""
    assert mark_html("<!-- note --><p>only</p>", INFO, wrap=True).startswith("<!-- note --><p data-block-id=")


def test_mark_html_skips_tags_inside_a_leading_comment():
    result = mark_html("<!-- see <b>x</b> --><div>y</div>", INFO, wrap=True)

    assert result.startswith('<!-- see <b>x</b> --><div data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"')


def test_mark_html_injects_after_the_tag_name_on_a_later_line():
    result = mark_html('\n<!-- a -->\n  <SECTION\n class="x">y</SECTION>', INFO, wrap=False)

    assert result == (
        '\n<!-- a -->\n  <SECTION data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" data-block-type="text"'
        ' data-block-label="Text"\n class="x">y</SECTION>'
    )


def test_mark_html_wraps_text_after_element():
    assert _wraps("<p>x</p> outro")


def test_mark_html_is_safe_across_threads():
    """Concurrent renders (threaded servers) must not share parse state."""
    single = "<div>" + "<p>a</p>" * 200 + "</div>"
    multi = "<p>a</p>" * 200
    errors = []
    barrier = threading.Barrier(8)

    def render(html, wraps):
        barrier.wait()
        for _ in range(15):
            try:
                if _wraps(html) is not wraps:
                    errors.append("wrong wrap decision")
            except Exception as exc:  # A shared parser raises mid-parse.
                errors.append(repr(exc))

    threads = [threading.Thread(target=render, args=(multi, True) if i % 2 else (single, False)) for i in range(8)]
    interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        sys.setswitchinterval(interval)

    assert errors == []


def test_mark_html_wraps_text_before_element():
    assert _wraps("intro<p>x</p>")


def test_mark_html_does_not_wrap_single_div():
    assert not _wraps('<div class="md"><p>a</p></div>')


def test_mark_html_does_not_wrap_lone_void_element():
    """A lone void element is still a single top-level root."""
    assert not _wraps('<img src="/x.png" alt="">')


def test_mark_html_wraps_void_element_followed_by_block_element():
    assert _wraps("<img><p>a</p>")


def test_mark_html_does_not_wrap_br_inside_single_p():
    """Void tags inside a non-void wrapper do not create extra top-level roots."""
    assert not _wraps("<p>line<br>break</p>")


def test_mark_html_does_not_mark_twice():
    """render_as_block calls render, so the same output can come through twice."""
    once = mark_html("<section>x</section>", INFO, wrap=True)

    assert mark_html(once, INFO, wrap=True) == once


def test_mark_html_marks_parent_over_a_childs_id():
    result = mark_html('<h2 data-block-id="child">x</h2>', INFO, wrap=False)

    assert result.startswith('<h2 data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"')


# ---------------------------------------------------------------------------
# _mark: only inside a scope, only for blocks with an id
# ---------------------------------------------------------------------------


def test_mark_skips_block_without_id_even_when_active():
    """Plain BoundBlock instances (no .id) must never be marked."""
    token = _open()
    try:
        assert _mark(_BoundBlockWithoutId(), "hello") == "hello"
    finally:
        _close(token)


def test_mark_skips_outside_a_scope():
    assert not is_marking()
    assert _mark(_BoundBlockWithId(), "<p>hello</p>") == "<p>hello</p>"


def test_list_child_proxy_len_and_bool():
    class _Item(blocks.StructBlock):
        title = blocks.CharBlock()

        class Meta:
            label = "Item"

    list_block = blocks.ListBlock(_Item())
    list_value = list_block.to_python([{"title": "a"}, {"title": "b"}])

    token = _open()
    try:
        proxies = list(_patched_list_iter(list_value))
    finally:
        _close(token)

    assert len(proxies[0]) == 1
    assert bool(proxies[0]) is True
    assert len(proxies[1]) == 1
    assert bool(proxies[1]) is True


def test_list_child_proxy_bool_false_for_empty_string_char_child():
    list_block = blocks.ListBlock(blocks.CharBlock())
    list_value = list_block.to_python([""])

    token = _open()
    try:
        proxy = list(_patched_list_iter(list_value))[0]
    finally:
        _close(token)

    assert bool(proxy) is False


# ---------------------------------------------------------------------------
# install() idempotency
# ---------------------------------------------------------------------------


def test_install_is_idempotent():
    """install() runs on every marking() / register_page_marker() call.
    Calling it again must not overwrite the stored original — if it did,
    _originals["BoundBlock.render"] would point to the patched version,
    causing infinite recursion on every block render.
    """
    original_before = patches_module._originals["BoundBlock.render"]
    install()
    assert patches_module._originals["BoundBlock.render"] is original_before
    assert BoundBlock.render is _patched_render


# ---------------------------------------------------------------------------
# ListValue.__iter__ patch (preview-gated)
# ---------------------------------------------------------------------------


def test__patched_list_iter_yields_plain_values_when_preview_inactive():
    """Outside preview, iteration matches stock Wagtail (plain child values)."""

    class _Item(blocks.StructBlock):
        title = blocks.CharBlock()

        class Meta:
            label = "Item"

    list_block = blocks.ListBlock(_Item())
    list_value = list_block.to_python([{"title": "a"}, {"title": "b"}])

    assert not is_marking()
    iterated = list(_patched_list_iter(list_value))
    assert len(iterated) == 2
    assert iterated[0] is list_value.bound_blocks[0].value
    assert iterated[1] is list_value.bound_blocks[1].value


def test__patched_list_iter_preview_yields_proxies_with_bound_block_face():
    """During preview, each item is a _ListChildProxy: .id and render_as_block
    for inspect, while .value matches the underlying ListChild.value.
    """

    class _Item(blocks.StructBlock):
        title = blocks.CharBlock()

        class Meta:
            label = "Item"

    list_block = blocks.ListBlock(_Item())
    list_value = list_block.to_python([{"title": "a"}, {"title": "b"}])

    token = _open()
    try:
        iterated = list(_patched_list_iter(list_value))
    finally:
        _close(token)

    assert len(iterated) == 2
    for i, proxy in enumerate(iterated):
        assert isinstance(proxy, _ListChildProxy)
        assert proxy.id == list_value.bound_blocks[i].id
        assert proxy.value is list_value.bound_blocks[i].value
        assert hasattr(proxy, "render_as_block")


def test__patched_list_iter_preview_proxy_delegates_struct_fields():
    """Dot and key access resolve like the plain StructValue (mapping tried first)."""

    class _Item(blocks.StructBlock):
        title = blocks.CharBlock()

        class Meta:
            label = "Item"

    list_block = blocks.ListBlock(_Item())
    list_value = list_block.to_python([{"title": "nested"}])

    token = _open()
    try:
        proxy = list(_patched_list_iter(list_value))[0]
    finally:
        _close(token)

    assert proxy.title == "nested"
    assert proxy["title"] == "nested"


def test__patched_list_iter_preview_proxy_iterates_stream_value():
    """``for block in item`` in templates maps to iter(proxy.value) for StreamValue children."""
    stream_block = blocks.StreamBlock([("text", blocks.CharBlock())])
    list_block = blocks.ListBlock(stream_block)
    # One list item = one stream (list of block dicts)
    list_value = list_block.to_python([[{"type": "text", "value": "hello"}]])

    token = _open()
    try:
        proxy = list(_patched_list_iter(list_value))[0]
    finally:
        _close(token)

    inner = list(proxy)
    assert len(inner) == 1
    assert inner[0].value == "hello"


def test__patched_list_iter_preview_proxy_str_uses_plain_value():
    """``{{ item }}`` should stringify the child value, not BoundBlock HTML."""
    list_block = blocks.ListBlock(blocks.CharBlock())
    list_value = list_block.to_python(["plain"])

    token = _open()
    try:
        proxy = list(_patched_list_iter(list_value))[0]
    finally:
        _close(token)

    assert str(proxy) == "plain"


def test_list_value_iteration_uses_patched_iter_on_class_non_preview():
    """``list(ListValue)`` with preview off yields plain values."""

    class _Item(blocks.StructBlock):
        title = blocks.CharBlock()

        class Meta:
            label = "Item"

    list_block = blocks.ListBlock(_Item())
    list_value = list_block.to_python([{"title": "x"}])

    assert not is_marking()
    iterated = list(list_value)
    assert len(iterated) == 1
    assert iterated[0] is list_value.bound_blocks[0].value


def test_list_value_iteration_uses_patched_iter_on_class_preview():
    """``list(ListValue)`` with preview on yields _ListChildProxy instances."""

    class _Item(blocks.StructBlock):
        title = blocks.CharBlock()

        class Meta:
            label = "Item"

    list_block = blocks.ListBlock(_Item())
    list_value = list_block.to_python([{"title": "x"}])

    token = _open()
    try:
        iterated = list(list_value)
    finally:
        _close(token)

    assert len(iterated) == 1
    assert isinstance(iterated[0], _ListChildProxy)
    assert iterated[0].value is list_value.bound_blocks[0].value


def test_list_value_iter_patch_applied_at_startup():
    """install() replaces ListValue.__iter__ exactly once."""
    assert "ListValue.__iter__" in patches_module._originals
    assert ListValue.__dict__.get("__iter__") is _patched_list_iter
