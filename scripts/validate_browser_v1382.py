"""Run browser suites against fresh synthetic hosts, preserving real rate limits.

Requires a built frontend, installed Chrome, Python test dependencies and npm ci.
Only fixtures are launched. No deployment, production database or real sends.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'general': [('general-search', 'unified'), ('unified-search', 'unified'), ('map-search', 'unified'), ('smart-search', 'unified'), ('absorption', 'unified'), ('autonomy', 'unified'), ('experience', 'unified'), ('workflow', 'unified')],
    'integration': [('absorption', 'unified'), ('unified-search', 'unified'), ('workflow', 'unified')],
    'a': [('redesign', 'unified'), ('workflow', 'unified'), ('learning', 'unified'), ('experience', 'unified')],
    'b': [('unified-search', 'unified'), ('smart-search', 'unified'), ('map-search', 'unified'),
          ('autonomy', 'unified'), ('intelligence', 'intelligence'), ('communication', 'communication')],
}

GROUPS['complete']=GROUPS['general']+[('absorption-intelligent','unified'),('redesign','unified'),('learning','unified'),('intelligence','intelligence'),('communication','communication')]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=GROUPS, required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--suite', help='One suite from the selected group')
    args=parser.parse_args()
    output=ROOT/'artifacts';output.mkdir(exist_ok=True)
    report=[]
    suites=GROUPS[args.group]
    if args.suite:
        suites=[pair for pair in suites if pair[0]==args.suite]
        if not suites:parser.error('Suite is not in the selected group')
    for index,(suite,fixture) in enumerate(suites):
        port=args.port+index
        if (ROOT/f'data/e2e-{port}.db').exists():
            raise RuntimeError('Choose a new port: fixture database already exists')
        env={**os.environ,'E2E_PORT':str(port),'E2E_ORIGIN':f'http://localhost:{port}',
             'E2E_PYTHON':sys.executable,'TEMP':str(output/'tmp'),'TMP':str(output/'tmp')}
        with (output/f'host-{suite}-{port}.log').open('w',encoding='utf-8') as hostlog:
            host=subprocess.Popen([sys.executable,f'tests/{fixture}_browser_fixture.py','server'],cwd=ROOT,
                env=env,stdout=hostlog,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            try:
                for _ in range(60):
                    if host.poll() is not None:raise RuntimeError('Fixture exited; inspect host log')
                    try:
                        with urlopen(f'http://localhost:{port}/api/health',timeout=1):break
                    except Exception:time.sleep(.5)
                else:raise RuntimeError('Fixture did not become ready')
                start=time.monotonic()
                with (output/f'e2e-{suite}-release.txt').open('w',encoding='utf-8') as log:
                    result=subprocess.run([shutil.which('node'),'node_modules/@playwright/test/cli.js','test',
                        f'e2e/{suite}.spec.ts','--reporter=list','--output',f'../artifacts/browser-{suite}'],
                        cwd=ROOT/'frontend',env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
                report.append({'suite':suite,'port':port,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,2)})
                print(json.dumps(report[-1]),flush=True)
                (output/f'browser-{args.suite or ("group-"+args.group)}.json').write_text(json.dumps(report,indent=2))
            finally:
                if host.poll() is None:
                    if os.name=='nt':
                        subprocess.run(['taskkill','/PID',str(host.pid),'/T','/F'],capture_output=True)
                    else:host.terminate()
                    host.wait(timeout=15)
    if any(row['exit_code'] for row in report):raise SystemExit(1)


if __name__=='__main__':main()
