# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0]

### Changed

- List children are now marked with the type and label the walk gives them, taken from
  the list's field name: a `tags` list's items are marked `tag` / `Tag`, not
  `item` / `Item`. Tools that match the HTML against `blocks_for_field` now agree.
- `blocks_for_field` yields `BlockInfo` named tuples. They still unpack as
  `(id, type, label, parent_id)`.

### Added

- `describe(child, *, list_block=None, parent_id=None)`: the `BlockInfo` for one stream
  or list child, named the way the walk and the marks both name it.
- Wagtail 8 in the tested versions and the tox matrix.

### Fixed

- Marking is thread-safe. Concurrent renders shared one HTML parser, which could pick the
  wrong wrap decision or raise mid-render.
- A tag inside a leading HTML comment no longer gets the attributes; the first real
  element does.

## [0.1.0]

### Added

- First release: block marking and the StreamField walk, extracted from wagtail-inspect
  0.1.1 and wagtail-live-comments 0.1.0, which now depend on this package.
- `register_page_marker`, `marking`, `is_marking`, and opt-in `display:contents`
  wrapping.
