"""Prepare local version labels and the existing browser runner for this cycle."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
for name in ('frontend/package.json','frontend/package-lock.json','frontend/src/ecosystemBridge.ts','frontend/src/pages/About.tsx'):
    path=root/name
    if path.exists(): path.write_text(path.read_text(encoding='utf-8').replace('1.38.6-dev','1.38.7-dev'),encoding='utf-8')
source=(root/'scripts/validate_browser_v1386.py').read_text(encoding='utf-8')
source=source.replace("GROUPS['operations']=", "GROUPS['planning']=[('planning','planning')]\nGROUPS['operations']=")
(root/'scripts/validate_browser_v1387.py').write_text(source,encoding='utf-8')
print('Version labels and browser runner prepared.')
readme=root/'README.md'
content=readme.read_text(encoding='utf-8')
if not content.startswith('## v1.38.7-dev'):
    readme.write_text('''## v1.38.7-dev — Planejamento de prospecção

Plano diário em Automações, com autorização explícita, limites persistentes e execução pelo worker existente. Revisão **033 sobre 032**. Pacote de desenvolvimento; sem deploy ou homologação externa.

- [Instalação e PATCH](docs/INSTALL-v1.38.7-dev.md)
- [Arquitetura e contratos](docs/ARCHITECTURE-v1.38.7-dev.md)
- [Metas e indicadores](docs/METRICS-v1.38.7-dev.md)
- [Validação](docs/VALIDATION-v1.38.7-dev.md)
- [Changelog](docs/CHANGELOG-v1.38.7-dev.md)
- [Checkpoint](docs/CHECKPOINT-v1.38.7-dev.md)

'''+content,encoding='utf-8')
