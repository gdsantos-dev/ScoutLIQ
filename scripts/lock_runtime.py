"""Resolve installed runtime dependencies without including test/dev tools."""
from importlib.metadata import distributions
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

packages={canonicalize_name(d.metadata['Name']):d for d in distributions()}
queue=[Requirement(line).name for line in Path('requirements.txt').read_text().splitlines() if line.strip() and not line.startswith('#')]
seen=set()
output=[]
while queue:
    name=canonicalize_name(queue.pop())
    if name in seen:
        continue
    seen.add(name)
    distribution=packages[name]
    output.append(name+'=='+distribution.version)
    for raw in distribution.requires or []:
        requirement=Requirement(raw)
        if requirement.marker is None or requirement.marker.evaluate({'extra':''}):
            queue.append(requirement.name)
Path('requirements.lock').write_text('# Runtime lock. Re-audit before deployment.\n'+'\n'.join(sorted(output))+'\n',encoding='utf-8')
