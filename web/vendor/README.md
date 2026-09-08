# Vendored third-party libraries

Pinned, unmodified minified builds copied from npm so the static site is
self-contained (no CDN dependency, works offline once cached).

| File | Package | Version | License |
|------|---------|---------|---------|
| vis-network.min.js | vis-network (standalone UMD) | 9.1.9 | MIT / Apache-2.0 |
| plotly.min.js | plotly.js-dist-min | 2.35.2 | MIT |
| jszip.min.js | jszip | 3.10.1 | MIT / GPLv3 dual |

To upgrade: `npm pack <pkg>@<version>` and copy the same file paths.
