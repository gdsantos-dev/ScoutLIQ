"""Disposable test databases. PostgreSQL requires an explicit loopback test URL."""
import os
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def postgres_database(raw):
    url = make_url(raw)
    if (url.drivername != 'postgresql+psycopg' or url.host not in ('127.0.0.1', 'localhost', '::1')
            or not (url.database or '').startswith('scoutliq_test_') or url.query):
        raise RuntimeError('PostgreSQL tests require a loopback scoutliq_test_ database without URL options.')
    schema = 'scoutliq_test_' + uuid4().hex
    admin = create_engine(url, connect_args={'connect_timeout': 5}, hide_parameters=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = url.update_query_dict({'options': '-csearch_path=' + schema})

    def cleanup():
        # Only the freshly generated schema, never the database or public schema.
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()

    return isolated.render_as_string(hide_password=False), cleanup
