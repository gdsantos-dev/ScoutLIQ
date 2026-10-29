"""Consistent SQLite backup using SQLite backup API, including active WAL data."""
import argparse
import sqlite3
from pathlib import Path

parser=argparse.ArgumentParser(description='Backup consistente do SQLite ScoutLIQ')
parser.add_argument('--source',required=True)
parser.add_argument('--destination',required=True)
args=parser.parse_args()
source=Path(args.source).resolve()
destination=Path(args.destination).resolve()
if not source.is_file() or source==destination or destination.exists():
    raise SystemExit('Origem deve existir e destino deve ser um novo arquivo diferente.')
destination.parent.mkdir(parents=True,exist_ok=True)
with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(destination) as dst:
    src.backup(dst)
    result=dst.execute('PRAGMA integrity_check').fetchone()[0]
    if result!='ok':
        raise SystemExit('Falha na verificação do backup')
print('Backup criado e verificado.')
