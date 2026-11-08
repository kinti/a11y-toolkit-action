# a11y-toolkit-action

Audit URLs with the [a11y-toolkit](https://github.com/kinti/a11y-toolkit)
engine from GitHub Actions: an honest 0-100 score per URL with beyond-axe
signals (contrast over images, 320px reflow, low-quality alt text, keyboard
traps, auto-complete, and more), a step-summary + SARIF artifact, and one
GitHub issue per signal+URL — **reopened on regression, closed when
resolved, frozen by the `wontfix` label**.

Inspired by the loop GitHub's own accessibility-scanner teaches; running a
different engine on purpose (and shipping the evidence, not just tickets).

## Quickstart

```yaml
name: a11y audit
on:
  workflow_dispatch:
  schedule: [{cron: '0 6 * * 1'}]
jobs:
  audit:
    runs-on: ubuntu-latest
    permissions: {issues: write, contents: read}
    steps:
      - uses: kinti/a11y-toolkit-action@v1
        with:
          urls: |
            https://your.site
            https://your.site/pricing
        # fail-on: high        # optional: fail CI on high findings
```

`GITHUB_TOKEN` works by default (issues:write). Findings group one issue
per signal per URL; a finding that vanishes closes its issue, and returns
reopen it. Add `wontfix` to keep an issue closed.

## Inputs

| Input | Default | What |
|---|---|---|
| `urls` | — | Newline-delimited list of public URLs (optional when `sitemap` is set) |
| `sitemap` | — | sitemap.xml URL, parsed by the engine and deduped against `urls` |
| `create-issues` | `true` | File/update issues (`false` = report only) |
| `labels` | `a11y-toolkit` | Labels the action owns |
| `fail-on` | `none` | Exit 1 at `medium` or `high` |
| `lang` | `en` | `en` \| `es` findings |
| `token` | `github.token` | Needs `issues:write` when filing |

## Sitemaps

```yaml
      - uses: kinti/a11y-toolkit-action@v1
        with:
          sitemap: https://your.site/sitemap.xml   # deduped against urls
          urls: |
            https://your.site/pricing              # explicit first, always
```

The engine parses the sitemap itself (no crawler to trust); explicit
`urls` run first and sitemap URLs join deduped after them.

## Findings are untrusted page content

Alt text, link text, form names — every example in a filed issue comes
from the PAGE being audited, i.e. from content your site's owner does not
control when you audit someone else's. This action wraps page-derived
strings in code spans and never renders them as markdown/HTML, and the
engine's own prose is the only free text. Treat scanner output as
untrusted anywhere it flows (issue bodies, Copilot prompts, agents):
their issue #292/#259 is our doctrine from day one.

## Honesty

Automated screening covers part of WCAG — every issue and summary says so.
A clean run is not conformance. If you need a signed, verifiable record
(VPAT/OpenACR, EN 301 549, tender annexes), that is
[a11y.es](https://a11y.es)'s job.

## How it differs from github/accessibility-scanner

Same loop (scan → issues → fix upstream), different engine: this action
runs the a11y-toolkit's own rule set — signals axe-core does not emit
(pixel-sampled contrast over images, 320px reflow, target size, alt
quality), es/en findings, EN 301 549 / RGAA / Section 508 clause mapping in
the full report, and an SHA-256-sealed evidence pack on demand. Stateless
by design: the issues are the ledger — no cache branch.

License: MIT.
