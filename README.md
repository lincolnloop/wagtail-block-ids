# Wagtail Block IDs

Marks rendered StreamField blocks with `data-block-id`, `data-block-type` and
`data-block-label`, so front-end tools can map the page back to the blocks that
produced it. It is the shared core of
[wagtail-inspect](https://github.com/lincolnloop/wagtail-inspect) and
[wagtail-live-comments](https://github.com/lincolnloop/wagtail-live-comments), until
Wagtail marks blocks itself.

It is a library, not a Django app: nothing goes in `INSTALLED_APPS`. Apps that use it
say when to mark.

```python
from wagtail_block_ids import register_page_marker


class MyAppConfig(AppConfig):
    def ready(self):
        # Mark live and preview serves for editors of the page.
        register_page_marker(lambda page, request: user_can_edit(page, request.user))
```

- `register_page_marker(should_mark, *, wrap=False)`: on every `Page.serve` and
  `serve_preview`, mark the render if any registered `should_mark(page, request)`
  returns true.
- `marking(*, wrap=False)`: a context manager that marks everything rendered inside it.
- `is_marking()`: whether a scope is open.
- `blocks_for_field(stream_value)`, `stream_values(page)`, `block_ids(page)`,
  `resolve_block_type(...)` and `resolve_block_label(...)`: walk StreamField values
  the same way the marks are made.

## Marking rules

- The attributes go on the first element of each block's output. Stream children
  and list children (through `{% include_block %}`) are marked at every depth.
- **Wrapping is opt-in.** If any active scope or willing marker passed `wrap=True`,
  output with no root element, or several, is wrapped in
  `<div style="display:contents">`. Otherwise only the first root is marked and a
  block with no root element stays unmarked. Wrappers can break grid and flex layouts.
- Requests no marker accepts are untouched.

## Sharing the page between block tools

Tools that highlight blocks on hover (inspect, live comments) must not run at once,
or every hover and click is handled twice. They coordinate in the browser with one
event, so neither needs to know about the other:

- When a mode turns on, dispatch on `document`:
  `new CustomEvent("wagtail-block-ids:mode-on", { detail: { source: "<your package>" } })`.
- Listen for that event, and turn your mode off when `detail.source` isn't yours.
- Mark your own UI that sits on the page (comment pins, popovers) with
  `data-block-ids-ignore`, and never give it `data-block-id`. Block modes ignore
  hovers, clicks and keys on anything inside `[data-block-ids-ignore]`, so it is not
  highlighted, and it doesn't count as part of the block it sits in.

## Development

```sh
uv sync --extra testing
uv run pytest
uvx --with tox-uv tox   # Django 4.2–6.0 × Wagtail 5–7
```
