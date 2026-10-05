# Landing page

`index.html` is the one-page marketing site for Auto-sync-LRC, published with
GitHub Pages by [`.github/workflows/pages.yml`](../.github/workflows/pages.yml)
on every push to `main` that touches `site/`. It is plain HTML and CSS with no
build step: open `index.html` in a browser to preview it.

Published at <https://rhapta-toddler.github.io/Auto-sync-LRC/>.

## One-time setup

1. **Turn on Pages:** repo *Settings > Pages > Build and deployment > Source:
   GitHub Actions*. Then re-run the *Deploy landing page* workflow (or push a
   change under `site/`).
2. **Turn on visit counting:** create a free site at
   <https://www.goatcounter.com> (no cookies, no personal data, so no cookie
   banner is needed), then put its code in `GOATCOUNTER_CODE` near the bottom
   of `index.html`. Page views and clicks on the download buttons
   (`download-windows`, `download-windows-install`) then show up in the
   GoatCounter dashboard.

## Counting downloads

Every download of the installer is counted by GitHub itself, whether it came
from this page or anywhere else. The page shows the running total next to the
download button once it reaches 10. To read it yourself:

```
gh api repos/rhapta-toddler/Auto-sync-LRC/releases --jq '[.[].assets[] | select(.name=="Auto-sync-LRC-Setup.exe") | .download_count] | add'
```

## When things change

- New release: nothing to do, the download link always points at the latest
  release and the version and size are read live. Update `softwareVersion` in
  the JSON-LD block if you want search engines to see the new number.
- Moved domain or repo: update the canonical URL, `og:url`, the JSON-LD URLs,
  `robots.txt`, `sitemap.xml` and `llms.txt`. `tests/test_site.py` checks that
  they stay consistent.
