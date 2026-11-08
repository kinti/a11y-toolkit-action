#!/usr/bin/env python3
"""Pure-logic tests for the action: issue planning (the ledger semantics)
and the summary. No network, no gh."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from entry import (issue_key, plan_issue_ops, build_summary,  # noqa: E402
                   merge_urls)

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(('ok  ' if cond else 'FAIL') + ' ' + name)


K1 = issue_key('https://x.dev', 'img_no_alt', '1.1.1')
K2 = issue_key('https://x.dev', 'alt_quality', '1.1.1')
F1 = {'key': K1, 'body': 'b1', 'severity': 'high'}
F2 = {'key': K2, 'body': 'b2', 'severity': 'medium'}
TODAY = '2026-11-06'

# create: no history → one create per finding, keyed by signal+URL
ops = plan_issue_ops([], [F1, F2], TODAY)
check('no history → creates', [o['op'] for o in ops] == ['create', 'create']
      and ops[0]['title'] == K1)

# still present (open) → comment, never duplicate
ops = plan_issue_ops([{'number': 1, 'title': K1, 'state': 'open',
                       'labels': ['a11y-toolkit']}], [F1], TODAY)
check('open match → comment (no dup)', ops == [{'op': 'comment', 'number': 1,
                                                'body': f'Still present on {TODAY}.'}])

# regression: closed issue found again → reopen + comment
ops = plan_issue_ops([{'number': 2, 'title': K1, 'state': 'closed',
                       'labels': []}], [F1], TODAY)
check('closed match → reopen', ops[0]['op'] == 'reopen'
      and ops[0]['number'] == 2)

# wontfix: frozen — found again on a closed issue stays closed
ops = plan_issue_ops([{'number': 3, 'title': K1, 'state': 'closed',
                       'labels': ['wontfix']}], [F1], TODAY)
check('wontfix stays closed', ops[0]['op'] == 'none')

# resolved: open issue whose key vanished this run → close
ops = plan_issue_ops([{'number': 4, 'title': K2, 'state': 'open',
                       'labels': []}], [F1], TODAY)
closes = [o for o in ops if o['op'] == 'close']
check('vanished → close', len(closes) == 1 and closes[0]['number'] == 4)

# mixed run: one persists (comment), one vanishes (close), one new (create)
ops = plan_issue_ops(
    [{'number': 10, 'title': K1, 'state': 'open', 'labels': []},
     {'number': 11, 'title': K2, 'state': 'open', 'labels': []}],
    [F1], TODAY)
check('mixed run → comment+close', sorted(o['op'] for o in ops)
      == ['close', 'comment'])

# key is per signal AND per URL
check('key separates URLs',
      issue_key('https://a.dev', 's', '1.1.1') != issue_key('https://b.dev',
                                                            's', '1.1.1'))

# summary carries scores + the honest line
sm = build_summary([{'url': 'https://x.dev',
                     'report': {'score': 62, 'summary': {'high': 1,
                                                         'medium': 2,
                                                         'low': 3}}}])
check('summary has score and honesty',
      '**62**' in sm and 'not conformance' in sm)

fails = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks")
sys.exit(1 if fails else 0)

# ── merge_urls: explícito primero, sitemap después, dedupe por barra final ──
m = merge_urls('https://a.dev\nhttps://b.dev/',
               ['https://c.dev', 'https://b.dev/', 'https://d.dev'])
check('merge order+dedupe', m == ['https://a.dev', 'https://b.dev',
                                  'https://c.dev', 'https://d.dev'])
check('merge empty explicit', merge_urls('', ['https://x.dev'])
      == ['https://x.dev'])
check('merge nothing', merge_urls('', []) == [])
