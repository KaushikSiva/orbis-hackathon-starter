#!/usr/bin/env python3
"""Run a bounded Qoder test task without printing credentials or loading unrelated tools."""
from pathlib import Path
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

root=Path(__file__).resolve().parents[1]
env=os.environ.copy()
for line in (root/'.env').read_text().splitlines():
    if line.startswith('QODER_PERSONAL_ACCESS_TOKEN='):
        value=line.split('=',1)[1].strip().strip('"').strip("'")
        if value: env['QODER_PERSONAL_ACCESS_TOKEN']=value
if not env.get('QODER_PERSONAL_ACCESS_TOKEN'):
    print('Qoder task not run: QODER_PERSONAL_ACCESS_TOKEN is not configured.')
    sys.exit(2)
prompt=(root/'docs/evidence/qoder-task.txt').read_text()
cmd=[str(root/'tooling/node_modules/.bin/qoder'),'--print','--output-format','json','--permission-mode','accept_edits','--no-session-persistence','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--disallowed-tools','Bash,WebFetch,WebSearch,Task','--cwd',str(root),prompt]
result=subprocess.run(cmd,cwd=root,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
text=result.stdout
for key,value in env.items():
    if any(s in key for s in ('TOKEN','SECRET','API_KEY','PASSWORD')) and len(value)>5:
        text=text.replace(value,'[REDACTED]')
output=root/'docs/evidence/qoder-transcript.txt'
output.write_text('Qoder task executed '+datetime.now(timezone.utc).isoformat()+'\nExit code: '+str(result.returncode)+'\n\n'+text)
print(json.dumps({'exit_code':result.returncode,'evidence':str(output.relative_to(root)),'test_created':(root/'backend/test_qoder_journey.py').exists()}))
sys.exit(result.returncode)
