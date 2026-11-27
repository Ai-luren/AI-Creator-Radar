"""Exercise bounded persistence with a fake remote, including ambiguous push outcomes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAKE_GIT = """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
p=Path(os.environ['FAKE_GIT_STATE'])
state=json.loads(p.read_text())
args=sys.argv[1:]
state['calls'].append(args)
code=0
if args[0]=='rev-parse':
    print(state['head'] if args[1]=='HEAD' else state['remote'])
elif args[0]=='fetch':
    state['fetches']+=1
    if state['fetches']<=state.get('fail_fetches',0): code=1
elif args[0]=='diff': code=1
elif args[0]=='commit': state['head']='candidate'
elif args[0]=='push':
    state['pushes']+=1
    mode=state['mode']
    if mode=='lost-response':
        state['remote']='candidate'; code=1
    elif mode=='concurrent':
        state['remote']='new-main'; code=1
    elif mode=='fail': code=1
    elif mode=='retry' and state['pushes']==1: code=1
    else: state['remote']='candidate'
elif args[0] not in ('config','add'): code=99
p.write_text(json.dumps(state))
sys.exit(code)
"""


class PersistDataTests(unittest.TestCase):
    def run_case(self, mode, fail_fetches=0):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            commands=root/'bin'; commands.mkdir()
            for name, content in {
                'git':FAKE_GIT,
                'timeout':'#!/bin/sh\nshift\nexec "$@"\n',
                'sleep':'#!/bin/sh\nexit 0\n',
            }.items():
                path=commands/name; path.write_text(content); path.chmod(0o755)
            state=root/'state.json'
            state.write_text(json.dumps({'head':'base','remote':'base','calls':[],
                                        'pushes':0,'fetches':0,'mode':mode,'fail_fetches':fail_fetches}))
            output=root/'output'
            env={**os.environ,'PATH':str(commands)+os.pathsep+os.environ['PATH'],
                 'FAKE_GIT_STATE':str(state),'GITHUB_OUTPUT':str(output)}
            result=subprocess.run(['bash',str(ROOT/'scripts/persist_data.sh')],cwd=root,env=env,
                                  capture_output=True,text=True,timeout=20)
            return result,json.loads(state.read_text()),output.read_text() if output.exists() else ''

    def test_transient_fetch_and_push_retries_same_commit(self):
        result,state,output=self.run_case('retry',fail_fetches=1)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(state['pushes'],2)
        self.assertEqual(sum(c[0]=='commit' for c in state['calls']),1)
        self.assertEqual(output,'changed=true\n')

    def test_lost_push_response_is_reconciled_without_duplicate_write(self):
        result,state,output=self.run_case('lost-response')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(state['pushes'],1)
        self.assertEqual(output,'changed=true\n')

    def test_concurrent_main_preserved(self):
        result,state,output=self.run_case('concurrent')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(state['pushes'],1)
        self.assertEqual(state['remote'],'new-main')
        self.assertEqual(output,'changed=false\n')

    def test_persistent_network_failure_remains_visible(self):
        result,state,output=self.run_case('fail')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(state['pushes'],3)
        self.assertEqual(output,'')
        result,state,output=self.run_case('retry',fail_fetches=3)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(state['pushes'],0)
        self.assertEqual(output,'')
