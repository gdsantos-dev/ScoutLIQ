"""Fail closed on sensitive tracked files and high-confidence credential patterns."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'private_key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'github_token': rb'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}',
    'openai_token': rb'sk-(?:proj-)?[A-Za-z0-9_-]{35,}',
    'aws_key': rb'AKIA[0-9A-Z]{16}',
}


def inspect(name, data):
    path = Path(name)
    forbidden = (path.name == '.env' or (path.name.startswith('.env.') and path.name != '.env.example')
                 or path.suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.pem', '.key', '.p12', '.pfx', '.dump'}
                 or path.name.startswith(('credentials', 'client_secret', 'service-account'))
                 or any(part in {'node_modules', '.venv', 'backups', 'secrets'} for part in path.parts))
    return (['sensitive_path'] if forbidden else []) + [key for key, pattern in PATTERNS.items() if re.search(pattern, data)]


def main():
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    failures = []
    for name in filter(None, names):
        for reason in inspect(name, (ROOT / name).read_bytes()):
            failures.append(f'{name}: {reason}')  # Never print the matching value.
    if failures:
        print('\n'.join(failures))
        return 1
    print(f'Reviewed {len(list(filter(None, names)))} tracked paths; no forbidden files or known secret patterns.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
