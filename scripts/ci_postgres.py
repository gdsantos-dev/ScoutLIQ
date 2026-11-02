"""Create only the explicitly named ephemeral CI database and unprivileged role."""
import os
import psycopg
from psycopg import sql


def main():
    if os.getenv('GITHUB_ACTIONS') != 'true':
        raise SystemExit('This bootstrap is limited to the isolated Actions service.')
    with psycopg.connect(host='127.0.0.1', port=5432, dbname='postgres',
                        user='scoutliq_bootstrap', password='ci-ephemeral-bootstrap-only', autocommit=True) as db:
        db.execute(sql.SQL('CREATE ROLE scoutliq_tests LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}')
                   .format(sql.Literal('ci-ephemeral-tests-only')))
        db.execute('CREATE DATABASE scoutliq_test_ci OWNER scoutliq_tests')
        print('Ephemeral PostgreSQL ready; test role is not a superuser.')


if __name__ == '__main__':
    main()
