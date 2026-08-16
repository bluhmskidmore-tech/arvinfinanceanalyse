"""Cascade triage for css-dedup commits.

Three signals per (selector, prop), comparing commit^ vs commit:
  A. top-level winner value changed (affects widths where no media overrides)
  B. winner value changed inside a given @media context
  C. NEW cross-order risk: top-level block now sits after a media block sharing
     a property (the mechanism behind the confirmed regressions)
Any signal => commit is NOT "zero visual change" safe and needs full re-audit.
"""
import re
import subprocess
import sys

SIMPLE = re.compile(r'\.[A-Za-z0-9_-]+(::?[a-zA-Z-]+(\([^)]*\))?)?$')


def blocks(css: str):
    out = []
    i = 0
    n = len(css)
    media_stack = []
    buf = []
    while i < n:
        ch = css[i]
        if ch == '/' and css[i : i + 2] == '/*':
            j = css.find('*/', i + 2)
            i = (j + 2) if j != -1 else n
            continue
        if ch == '{':
            header = ' '.join(''.join(buf).split())
            buf = []
            if header.startswith('@'):
                media_stack.append(header)
                i += 1
                continue
            j = i + 1
            depth = 1
            while j < n and depth:
                if css[j] == '{':
                    depth += 1
                elif css[j] == '}':
                    depth -= 1
                j += 1
            ctx = media_stack[-1] if media_stack else ''
            out.append((header, i, ctx, css[i + 1 : j - 1]))
            i = j
            continue
        if ch == '}':
            if media_stack:
                media_stack.pop()
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    return out


def props(body: str):
    res = {}
    for part in body.split(';'):
        if ':' in part:
            k, v = part.split(':', 1)
            res[k.strip().lower()] = ' '.join(v.split())
    return res


def analyze(css: str):
    """Return (winners, seq): winners[(sel, ctx)][prop] = value; seq[sel] = [(pos, ctx, props)]."""
    winners = {}
    seq = {}
    for header, pos, ctx, body in blocks(css):
        pr = props(body)
        if not pr:
            continue
        for sel in (s.strip() for s in header.split(',')):
            if not SIMPLE.match(sel):
                continue
            winners.setdefault((sel, ctx), {}).update(pr)
            seq.setdefault(sel, []).append((pos, ctx, pr))
    return winners, seq


def cross_risk(seq):
    risky = {}
    for sel, occ in seq.items():
        media_pos = [p for p, c, _ in occ if c]
        if not media_pos:
            continue
        last_media = max(media_pos)
        for p, c, pr in occ:
            if not c and p > last_media:
                for mp, mc, mpr in occ:
                    if mc and mp < p:
                        shared = set(pr) & set(mpr)
                        # only conflicting values matter
                        conflict = {k for k in shared if pr[k] != mpr[k]}
                        if conflict:
                            risky.setdefault(sel, set()).update(conflict)
    return risky


def run(commit: str, path: str):
    def show(rev):
        r = subprocess.run(['git', 'show', f'{rev}:{path}'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        return r.stdout if r.returncode == 0 else None

    pre, post = show(f'{commit}^'), show(commit)
    if pre is None or post is None:
        return ['(file added/deleted — skip)']
    w_pre, s_pre = analyze(pre)
    w_post, s_post = analyze(post)
    findings = []
    keys = set(w_pre) | set(w_post)
    for key in sorted(keys):
        sel, ctx = key
        a, b = w_pre.get(key, {}), w_post.get(key, {})
        for prop in sorted(set(a) & set(b)):
            if a[prop] != b[prop]:
                where = ctx if ctx else 'top-level'
                findings.append(f'{sel} [{where}] {prop}: "{a[prop]}" -> "{b[prop]}"')
    r_pre, r_post = cross_risk(s_pre), cross_risk(s_post)
    for sel, propset in sorted(r_post.items()):
        added = propset - r_pre.get(sel, set())
        if added:
            findings.append(f'{sel} [cross-order NEW] conflicting: {", ".join(sorted(added))}')
    return findings


def main():
    commits = sys.argv[1:]
    for c in commits:
        r = subprocess.run(['git', 'show', c, '--name-only', '--format='], capture_output=True, text=True, encoding='utf-8', errors='replace')
        files = [f for f in r.stdout.split() if f.endswith('.css')]
        for f in files:
            findings = run(c, f)
            tag = 'CLEAN' if not findings else f'{len(findings)} FINDINGS'
            print(f'== {c[:9]} {f} : {tag}')
            for line in findings[:12]:
                print(f'   {line}')
            if len(findings) > 12:
                print(f'   ... and {len(findings) - 12} more')


if __name__ == '__main__':
    main()
