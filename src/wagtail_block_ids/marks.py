"""Mark rendered StreamField blocks with ``data-block-id`` / ``-type`` / ``-label``.

One set of patches, shared by every app that maps rendered HTML back to blocks:

- ``BoundBlock.render`` / ``render_as_block``: while marking, add the attributes to
  the first tag of each block's output (StreamChild is a BoundBlock, so top-level and
  nested stream children both get them). When a scope asked for wrapping, output with
  no root tag, or several roots, is wrapped in a ``display:contents`` div instead.
- ``ListValue.__iter__``: while marking, yield proxies so ``{% include_block item %}``
  over list children renders through ``BoundBlock`` and gets marked too.
- ``Page.serve`` / ``PreviewableMixin.serve_preview``: ask every registered marker
  whether this request should be marked; if any says yes, mark while serving and
  render lazy ``TemplateResponse``s before the scope ends.

Apps register with ``register_page_marker`` (from ``AppConfig.ready()``) or open a
``marking()`` scope around their own render. Patches install on first use, once.
"""

import contextlib
import logging
import re
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from dataclasses import dataclass
from html.parser import HTMLParser

from django.utils.html import conditional_escape, format_html, mark_safe
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.blocks import BoundBlock
from wagtail.blocks.list_block import ListValue
from wagtail.models import Page

try:
    from wagtail.models.preview import PreviewableMixin
except ImportError:  # pragma: no cover - Wagtail 5 layout
    from wagtail.models import PreviewableMixin

from .blocks import resolve_block_label, resolve_block_type

logger = logging.getLogger(__name__)

TESTED_WAGTAIL_VERSIONS = ((5,), (6,), (7,))

_originals: dict = {}


@dataclass(frozen=True)
class _Scope:
    wrap: bool


# ``None`` outside any marking scope.
_scope: ContextVar[_Scope | None] = ContextVar("wagtail_block_ids_scope", default=None)


@dataclass(frozen=True)
class _Marker:
    should_mark: Callable
    wrap: bool


_markers: list[_Marker] = []


def is_marking() -> bool:
    """Whether blocks rendered right now get marked."""
    return _scope.get() is not None


@contextlib.contextmanager
def marking(*, wrap: bool = False) -> Iterator[None]:
    """Mark every block rendered inside this block.

    ``wrap=True`` lets blocks without a single root element get a ``display:contents``
    wrapper. Nested scopes wrap if any of them asked to.
    """
    install()
    outer = _scope.get()
    token = _scope.set(_Scope(wrap=wrap or bool(outer and outer.wrap)))
    try:
        yield
    finally:
        _scope.reset(token)


def register_page_marker(should_mark: Callable, *, wrap: bool = False) -> None:
    """Mark page serves (live and preview) for which ``should_mark(page, request)`` is true.

    Call from ``AppConfig.ready()``. ``wrap`` as for ``marking()``.
    """
    install()
    _markers.append(_Marker(should_mark=should_mark, wrap=wrap))


# Matches the opening token of the first HTML element tag (e.g. "<div", "<section").
# Used by _inject_attrs_into_root to locate the injection point.
_FIRST_TAG_RE = re.compile(r"<[a-zA-Z][a-zA-Z0-9:-]*")

# Void elements have no closing tag and do not affect nesting depth.
_VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)


class _RootCounter(HTMLParser):
    def reset(self) -> None:
        super().reset()
        self.depth = 0
        self.roots = 0
        self.top_text = 0

    def handle_starttag(self, tag, _attrs) -> None:
        if not self.depth:
            self.roots += 1
        if tag not in _VOID_ELEMENTS:
            self.depth += 1

    def handle_endtag(self, tag) -> None:
        if tag not in _VOID_ELEMENTS:
            self.depth = max(0, self.depth - 1)

    def handle_data(self, data) -> None:
        if not self.depth and data.strip():
            self.top_text += 1


_root_counter = _RootCounter()


def _is_multi_root_fragment(html: str) -> bool:
    """True if fragment has multiple roots or text siblings (markdown-style)."""
    _root_counter.reset()
    _root_counter.feed(html)
    return _root_counter.roots > 1 or (_root_counter.roots == 1 and _root_counter.top_text > 0)


def _inject_attrs_into_root(output, block_id, block_type, block_label):
    """Insert ``data-block-*`` after the first start tag; return ``(out, ok)``."""
    attrs = (
        f' data-block-id="{conditional_escape(block_id)}"'
        f' data-block-type="{conditional_escape(block_type)}"'
        f' data-block-label="{conditional_escape(block_label)}"'
    )
    result, n = _FIRST_TAG_RE.subn(
        lambda m: m.group(0) + attrs,
        str(output),
        count=1,
    )
    if n:
        return mark_safe(result), True
    return output, False


def _wrapper(bound, content, block_type, block_label):
    return format_html(
        '<div data-block-id="{}" data-block-type="{}" data-block-label="{}" style="display:contents">{}</div>',
        bound.id,
        block_type,
        block_label,
        content,
    )


def _mark(bound, output):
    """Mark *bound*'s rendered *output* if a scope is open and the block has an id."""
    scope = _scope.get()
    if scope is None or not getattr(bound, "id", None):
        return output
    html = str(output)
    match = _FIRST_TAG_RE.search(html)
    if match:
        tag_end = html.find(">", match.end())
        first_tag = html[match.start() : tag_end if tag_end != -1 else len(html)]
        if f'data-block-id="{conditional_escape(bound.id)}"' in first_tag:
            return output  # Already marked (render_as_block calling render).
    block_type = resolve_block_type(bound)
    block_label = resolve_block_label(bound)
    if scope.wrap and (not match or _is_multi_root_fragment(html)):
        return _wrapper(bound, output if not match else mark_safe(html), block_type, block_label)
    annotated, _ = _inject_attrs_into_root(output, bound.id, block_type, block_label)
    return annotated


class _ListChildProxy:
    """While marking: ListChild with value-like access plus ``id`` / ``render_as_block``."""

    __slots__ = ("_child",)

    def __init__(self, list_child) -> None:
        object.__setattr__(self, "_child", list_child)

    id = property(lambda self: self._child.id)
    block = property(lambda self: self._child.block)
    block_type = property(lambda self: getattr(self._child, "block_type", None))
    value = property(lambda self: self._child.value)

    def render(self, context=None):
        return self._child.render(context)

    def render_as_block(self, context=None):
        return self._child.render_as_block(context)

    def __str__(self) -> str:
        return str(self._child.value)

    def __iter__(self):
        return iter(self._child.value)

    def __getattr__(self, name):
        v = self._child.value
        getitem = getattr(v, "__getitem__", None)
        if getitem is not None:
            try:
                return getitem(name)
            except (KeyError, TypeError, IndexError):
                pass
        return getattr(v, name)

    def __getitem__(self, key):
        return self._child.value[key]

    def __len__(self) -> int:
        return len(self._child.value)

    def __bool__(self) -> bool:
        return bool(self._child.value)


def _patched_render(self, context=None):
    return _mark(self, _originals["BoundBlock.render"](self, context=context))


def _patched_render_as_block(self, context=None):
    return _mark(self, _originals["BoundBlock.render_as_block"](self, context=context))


def _patched_list_iter(self):
    if not is_marking():
        return _originals["ListValue.__iter__"](self)
    return iter(_ListChildProxy(child) for child in self.bound_blocks)


def _marked_serve(page, request, serve):
    if is_marking():
        return serve()
    wanted = [marker for marker in _markers if marker.should_mark(page, request)]
    if not wanted:
        return serve()
    with marking(wrap=any(marker.wrap for marker in wanted)):
        response = serve()
        # TemplateResponse renders lazily, after this scope would be closed.
        if callable(getattr(response, "render", None)) and not getattr(response, "is_rendered", True):
            response.render()
        return response


def _patched_serve(self, request, *args, **kwargs):
    return _marked_serve(self, request, lambda: _originals["Page.serve"](self, request, *args, **kwargs))


def _patched_serve_preview(self, request, mode_name):
    original = _originals["PreviewableMixin.serve_preview"]
    return _marked_serve(self, request, lambda: original(self, request, mode_name))


def _apply_patch(target, attr, replacement, label) -> None:
    """Replace *attr* on *target* once; log failures without raising."""
    if label in _originals:
        return
    try:
        _originals[label] = getattr(target, attr)
        setattr(target, attr, replacement)
    except Exception:
        logger.exception("wagtail_block_ids: failed to patch %s", label)


def install() -> None:
    """Apply the patches (idempotent). ``marking`` and ``register_page_marker`` call this."""
    if _originals:
        return
    if not any(WAGTAIL_VERSION[: len(v)] == v for v in TESTED_WAGTAIL_VERSIONS):
        logger.warning(
            "wagtail_block_ids: Wagtail %s has not been tested. Tested versions: %s. Patches may not work correctly.",
            ".".join(str(x) for x in WAGTAIL_VERSION[:3]),
            ", ".join(".".join(str(x) for x in v) for v in TESTED_WAGTAIL_VERSIONS),
        )
    _apply_patch(BoundBlock, "render", _patched_render, "BoundBlock.render")
    _apply_patch(BoundBlock, "render_as_block", _patched_render_as_block, "BoundBlock.render_as_block")
    _apply_patch(ListValue, "__iter__", _patched_list_iter, "ListValue.__iter__")
    _apply_patch(Page, "serve", _patched_serve, "Page.serve")
    _apply_patch(PreviewableMixin, "serve_preview", _patched_serve_preview, "PreviewableMixin.serve_preview")
