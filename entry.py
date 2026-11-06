#!/usr/bin/env python3
"""a11y-toolkit GitHub Action — audit URLs, report, file issues.

The loop GitHub's own scanner taught the market, running OUR engine:
audit → one issue per signal+URL (reopened on regression, closed when
resolved, frozen by `wontfix`) → evidence artifact. Stateless by design:
the issues ARE the ledger — no cache branch to reset.

Honesty, as everywhere in this toolkit: automated screening covers part
of WCAG. Every issue and every summary says so. A clean run is not
conformance and a finding is not a verdict — it is a filter for the
human half.
"""

import datetime
import json
import os
import re
import subprocess
import sys

ENGINE_PIN = '5.27.0'          # keep in sync with action.yml
OUR_LABEL = 'a11y-toolkit'
SEV_ORDER = {'high': 3, 'medium': 2, 'low': 1}
HONEST_NOTE = (
    'Automated screening covers part of WCAG — this issue is a filter for '
    'the human half, not a conformance claim. Full review: https://a11y.es')


# ── pure helpers (unit-tested) ──────────────────────────────────────────────

def issue_key(url, signal, criterion_code):
    """Stable issue identity: one issue per signal+URL."""
    return f'[a11y] {signal} · {criterion_code} — {url}'


def plan_issue_ops(existing, findings, today):
    """Diff current findings against existing issues → ops.

    existing: [{number, title, state, labels:[names]}] (ours, any state)
    findings: [{key, title, body}]
    Returns ops: [{'op': 'create'|'comment'|'reopen'|'close', ...}].
    `wontfix` freezes an issue closed: it is never reopened.
    Close semantics: an OPEN issue of ours whose key was not found in this
    run is considered resolved (or the page changed) and gets closed."""
    by_key = {}
    for it in existing:
        key = it['title'].strip()
        by_key.setdefault(key, []).append(it)
    ops, seen = [], set()
    for f in findings:
        seen.add(f['key'])
        group = by_key.get(f['key'])
        if not group:
            ops.append({'op': 'create', 'title': f['key'], 'body': f['body']})
            continue
        it = group[0]                     # oldest first from gh --json
        labels = [x.lower() for x in it.get('labels', [])]
        if it['state'] == 'open':
            ops.append({'op': 'comment', 'number': it['number'],
                        'body': f'Still present on {today}.'})
        elif 'wontfix' in labels:
            ops.append({'op': 'none', 'number': it['number'],
                        'note': 'wontfix — stays closed'})
        else:
            ops.append({'op': 'reopen', 'number': it['number'],
                        'body': f'Back on {today} — reopening.'})
    for key, group in by_key.items():
        for it in group:
            if it['state'] == 'open' and it['title'].strip() not in seen:
                ops.append({'op': 'close', 'number': it['number'],
                            'body': ('Not detected on this run: fixed, or the '
                                     'page changed. Closing; it reopens by '
                                     'itself if the finding returns.')})
    return ops


def build_summary(results, lang='en'):
    """Markdown for $GITHUB_STEP_SUMMARY: per-URL score + findings."""
    lines = ['## a11y-toolkit audit', '']
    for r in results:
        if 'error' in r:
            lines.append(f'- `{r["url"]}` — ERROR: {r["error"]}')
            continue
        s = r['report'].get('summary', {})
        lines.append(f'- `{r["url"]}` — score **{r["report"].get("score")}** '
                     f'(high {s.get("high", 0)} · medium {s.get("medium", 0)} · '
                     f'low {s.get("low", 0)})')
    lines.append('')
    lines.append(f'_Automated screening covers part of WCAG — a filter, not '
                 f'conformance. Engine: a11y-toolkit {ENGINE_PIN}, '
                 f'{datetime.date.today().isoformat()}._')
    return '\n'.join(lines)


def finding_body(f, url, today):
    """Issue body: what, why, how — and the honest limit."""
    h = f.get('how', [])
    lines = [f'URL: {url}',
             f'Criterion: {f.get("criterion", "?")}',
             f'Severity: {f.get("severity", "?")}',
             '',
             f.get('issue', ''),
             '',
             '**How to fix**',
             f.get('remediation', ''),
             '']
    if f.get('examples'):
        lines.append('**Examples**')
        lines += [f'- `{x}`' for x in f['examples'][:5]]
    if f.get('paths'):
        lines.append('')
        lines.append('**Elements**')
        lines += [f'- `{p}`' for p in f['paths'][:5]]
    lines += ['', '---', HONEST_NOTE,
              f'_Engine a11y-toolkit {ENGINE_PIN} · {today}_']
    return '\n'.join(lines)


# ── gh plumbing ─────────────────────────────────────────────────────────────

def gh(*args, repo):
    env = dict(os.environ)
    return subprocess.run(
        ['gh'] + list(args) + ['-R', repo], capture_output=True, text=True,
        env=env)


def list_our_issues(repo, labels):
    r = gh('issue', 'list', '--state', 'all', '--limit', '500',
           '--json', 'number,title,state,labels',
           '--label', labels, repo=repo)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        return []
    out = []
    for it in json.loads(r.stdout or '[]'):
        it['labels'] = [x.get('name', '') for x in it.get('labels', [])]
        out.append(it)
    return out


# ── main ────────────────────────────────────────────────────────────────────

def main():
    urls = [u.strip() for u in os.environ.get('INPUT_URLS', '').split('\n')
            if u.strip()]
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    create_issues = (os.environ.get('INPUT_CREATE_ISSUES', 'true').lower()
                     == 'true')
    labels = os.environ.get('INPUT_LABELS', OUR_LABEL)
    fail_on = os.environ.get('INPUT_FAIL_ON', 'none').lower()
    lang = os.environ.get('INPUT_LANG', 'en')
    dry = '--dry-run' in sys.argv
    today = datetime.date.today().isoformat()

    if not urls:
        print('::error::INPUT_URLS is empty')
        return 1

    from a11y_toolkit.a11yaudit import audit_url, normalize_report
    results = []
    for u in urls:
        try:
            results.append({'url': u, 'report': normalize_report(
                audit_url(u, timeout=45, lang=lang))})
        except Exception as e:  # noqa: BLE001
            results.append({'url': u, 'error': f'{type(e).__name__}: {e}'})

    outdir = 'a11y-report'
    os.makedirs(outdir, exist_ok=True)
    json.dump(results, open(f'{outdir}/report.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    try:
        from a11y_toolkit.a11ysarif import sarif_from_report
        sar = sarif_from_report([r['report'] for r in results
                                 if 'report' in r])
        json.dump(sar, open(f'{outdir}/a11y.sarif', 'w',
                            encoding='utf-8'), ensure_ascii=False, indent=1)
    except Exception as e:  # noqa: BLE001
        print(f'::warning::SARIF skipped: {e}')

    summary = build_summary(results, lang)
    open(f'{outdir}/summary.md', 'w', encoding='utf-8').write(summary)
    spath = os.environ.get('GITHUB_STEP_SUMMARY')
    if spath:
        with open(spath, 'a', encoding='utf-8') as f:
            f.write(summary + '\n')

    findings = []
    for r in results:
        if 'report' not in r:
            continue
        for h in r['report'].get('findings', []):
            code = (h.get('criterion') or '').split(' ')[0]
            findings.append({
                'key': issue_key(r['url'], h.get('signal', '?'), code),
                'body': finding_body(h, r['url'], today),
                'severity': h.get('severity', 'low'),
                'title': f"{h.get('issue', 'finding')[:120]}",
            })

    # outputs
    scores = [r['report'].get('score') for r in results
              if 'report' in r and isinstance(r['report'].get('score'),
                                              (int, float))]
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as f:
            f.write(f'min-score={min(scores) if scores else ""}\n')
            f.write(f'findings={len(findings)}\n')

    # issues: create / comment / reopen / close — the issues ARE the ledger
    if create_issues and repo and not dry:
        ops = plan_issue_ops(list_our_issues(repo, labels), findings, today)
        for op in ops:
            if op['op'] == 'create':
                gh('issue', 'create', '--title', op['title'],
                   '--body', op['body'], '--label', labels, repo=repo)
            elif op['op'] == 'comment':
                gh('issue', 'comment', str(op['number']),
                   '--body', op['body'], repo=repo)
            elif op['op'] == 'reopen':
                gh('issue', 'reopen', str(op['number']), repo=repo)
                gh('issue', 'comment', str(op['number']),
                   '--body', op['body'], repo=repo)
            elif op['op'] == 'close':
                gh('issue', 'close', str(op['number']),
                   '--comment', op['body'], repo=repo)
        print(f'issue ops: {len(ops)}')
    elif dry:
        ops = plan_issue_ops([], findings, today)
        print(f'dry-run: would create {len(ops)} issues')

    worst = max((SEV_ORDER.get(f['severity'], 0) for f in findings),
                default=0)
    if SEV_ORDER.get(fail_on, 0) and worst >= SEV_ORDER[fail_on]:
        print('::error::findings at or above the fail-on threshold')
        return 1
    print(f'done: {len(findings)} findings across {len(results)} URLs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
