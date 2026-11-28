"""Compare the published site tree with the committed site, without credentials."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://ai-luren.github.io/AI-Creator-Radar/deploy-revision.json'
SHA = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')


def revision(root=ROOT):
    def git(ref):
        result = subprocess.check_output(['git', 'rev-parse', ref], cwd=root, text=True).strip()
        if not SHA.fullmatch(result):
            raise ValueError('Invalid Git revision')
        return result
    return {'commit': git('HEAD'), 'siteTree': git('HEAD:site')}


def status(expected, opener=urlopen):
    """Unknown transport/payload errors must not be treated as a stale site."""
    if not SHA.fullmatch(expected):
        raise ValueError('Invalid expected site tree')
    request = Request(URL + '?tree=' + expected, headers={'Cache-Control': 'no-cache', 'Accept': 'application/json'})
    try:
        with opener(request, timeout=8) as response:
            if response.geturl().split('?', 1)[0] != URL:
                return 'unknown'
            body = response.read(4097)
        if len(body) > 4096:
            return 'unknown'
        data = json.loads(body)
        if not isinstance(data, dict) or not SHA.fullmatch(str(data.get('commit', ''))):
            return 'unknown'
        if 'siteTree' not in data:
            return 'stale'  # migrate a valid legacy marker once
        tree = data['siteTree']
        if not isinstance(tree, str) or not SHA.fullmatch(tree):
            return 'unknown'
        return 'current' if tree == expected else 'stale'
    except HTTPError as exc:
        return 'stale' if exc.code == 404 else 'unknown'
    except (URLError, OSError, ValueError):
        return 'unknown'


def verify_live(expected, opener=urlopen, now=None):
    """Post-deploy proof of the exact site tree, not a self-certifying data audit."""
    if not SHA.fullmatch(expected):
        raise ValueError("Invalid expected site tree")
    result = status(expected, opener)
    return {"schema":"radar-live-publication/v1",
            "checkedAt":(now or datetime.now(timezone.utc)).isoformat(),
            "expectedSiteTree":expected,"status":result,
            "gate":"pass" if result=="current" else "unverified",
            "policy":"Marker matches the committed site tree; not proof of every asset or factual accuracy."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-marker', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify-live', action='store_true')
    parser.add_argument('--summary', type=Path)
    args = parser.parse_args()
    current = revision()
    if args.verify_live and args.write_marker:
        parser.error('--verify-live and --write-marker are mutually exclusive')
    if args.verify_live:
        proof=verify_live(current['siteTree'])
        proof.update(expectedCommit=current['commit'],runId=os.environ.get('GITHUB_RUN_ID'),
                     runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT'))
        print('Live publication proof:',json.dumps(proof,sort_keys=True))
        if args.summary:
            with args.summary.open('a',encoding='utf-8') as stream:
                stream.write('### Post-publication live marker\\n'+
                             '- Status: '+proof['gate']+' ('+proof['status']+')\\n'+
                             '- Checked: '+proof['checkedAt']+'\\n'+
                             '- Expected site tree: '+proof['expectedSiteTree']+'\\n'+
                             '- Expected commit: '+proof['expectedCommit']+'\\n')
        if proof['gate']!='pass':
            print('::warning::Live publication not verified; deployment API success alone is not acceptance.')
        return
    if args.write_marker:
        (ROOT / 'site/deploy-revision.json').write_text(json.dumps(current) + '\n', encoding='utf-8')
        print('Publishing revision:', current['commit'], 'site tree:', current['siteTree'])
        return
    result = status(current['siteTree'])
    print('Published site status:', result)
    if result == 'unknown':
        print('::warning::Unable to verify published marker; no recovery dispatch inferred from transport failure.')
    if args.output:
        with args.output.open('a', encoding='utf-8') as stream:
            stream.write('publication_status=' + result + '\n')


if __name__ == '__main__':
    main()
