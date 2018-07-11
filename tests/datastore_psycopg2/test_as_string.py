import pytest
import psycopg2
try:
    from psycopg2 import sql
except ImportError:
    sql = None

from utils import DB_SETTINGS, PSYCOPG2_VERSION
from newrelic.api.background_task import background_task


@pytest.fixture(scope='module')
def conn():
    conn = psycopg2.connect(
            database=DB_SETTINGS['name'], user=DB_SETTINGS['user'],
            password=DB_SETTINGS['password'], host=DB_SETTINGS['host'],
            port=DB_SETTINGS['port'])
    yield conn
    conn.close()


@pytest.mark.skipif(PSYCOPG2_VERSION < (2, 7), reason="Composable queries "
        "(from psycopg2 import sql) are not implemented before v2.7)")
@background_task()
def test_as_string_1(conn):

    # All of these are similar to those described in the doctests in
    # psycopg2/lib/sql.py

    comp = sql.Composed(
            [sql.SQL("insert into "), sql.Identifier("table")])
    result = comp.as_string(conn)
    assert result == 'insert into "table"'


@pytest.mark.skipif(PSYCOPG2_VERSION < (2, 7), reason="Composable queries "
        "(from psycopg2 import sql) are not implemented before v2.7)")
@background_task()
def test_as_string_2(conn):
    fields = sql.Identifier('foo') + sql.Identifier('bar')  # a Composed
    result = fields.join(', ').as_string(conn)
    assert result == '"foo", "bar"'


@pytest.mark.skipif(PSYCOPG2_VERSION < (2, 7), reason="Composable queries "
        "(from psycopg2 import sql) are not implemented before v2.7)")
@background_task()
def test_as_string_3(conn):
    query = sql.SQL("select {0} from {1}").format(
        sql.SQL(', ').join([sql.Identifier('foo'), sql.Identifier('bar')]),
        sql.Identifier('table'))
    result = query.as_string(conn)
    assert result == 'select "foo", "bar" from "table"'


@pytest.mark.skipif(PSYCOPG2_VERSION < (2, 7), reason="Composable queries "
        "(from psycopg2 import sql) are not implemented before v2.7)")
@background_task()
def test_as_string_4(conn):
    result = sql.SQL("select * from {0} where {1} = %s").format(
            sql.Identifier('people'), sql.Identifier('id')).as_string(conn)
    assert result == 'select * from "people" where "id" = %s'


@pytest.mark.skipif(PSYCOPG2_VERSION < (2, 7), reason="Composable queries "
        "(from psycopg2 import sql) are not implemented before v2.7)")
@background_task()
def test_as_string_5(conn):
    result = sql.SQL("select * from {tbl} where {pkey} = %s").format(
            tbl=sql.Identifier('people'), pkey=sql.Identifier('id')).as_string(
            conn)
    assert result == 'select * from "people" where "id" = %s'


@pytest.mark.skipif(PSYCOPG2_VERSION < (2, 7), reason="Composable queries "
        "(from psycopg2 import sql) are not implemented before v2.7)")
@background_task()
def test_as_string_6(conn):
    snip = sql.SQL(', ').join(
            sql.Identifier(n) for n in ['foo', 'bar', 'baz'])
    result = snip.as_string(conn)
    assert result == '"foo", "bar", "baz"'


@pytest.mark.skipif(PSYCOPG2_VERSION < (2, 7), reason="Composable queries "
        "(from psycopg2 import sql) are not implemented before v2.7)")
@background_task()
def test_as_string_7(conn):
    t1 = sql.Identifier("foo")
    t2 = sql.Identifier("ba'r")
    t3 = sql.Identifier('ba"z')
    result = sql.SQL(', ').join([t1, t2, t3]).as_string(conn)
    assert result == '"foo", "ba\'r", "ba""z"'


@pytest.mark.skipif(PSYCOPG2_VERSION < (2, 7), reason="Composable queries "
        "(from psycopg2 import sql) are not implemented before v2.7)")
@background_task()
def test_as_string_8(conn):
    s1 = sql.Literal("foo")
    s2 = sql.Literal("ba'r")
    s3 = sql.Literal(42)
    result = sql.SQL(', ').join([s1, s2, s3]).as_string(conn)
    assert result == "'foo', 'ba''r', 42"


@pytest.mark.skipif(PSYCOPG2_VERSION < (2, 7), reason="Composable queries "
        "(from psycopg2 import sql) are not implemented before v2.7)")
@background_task()
def test_as_string_9(conn):
    names = ['foo', 'bar', 'baz']
    q1 = sql.SQL("insert into table ({0}) values ({1})").format(
            sql.SQL(', ').join(map(sql.Identifier, names)),
            sql.SQL(', ').join(sql.Placeholder() * len(names)))
    result = q1.as_string(conn)
    assert (result ==
            'insert into table ("foo", "bar", "baz") values (%s, %s, %s)')


@pytest.mark.skipif(PSYCOPG2_VERSION < (2, 7), reason="Composable queries "
        "(from psycopg2 import sql) are not implemented before v2.7)")
@background_task()
def test_as_string_10(conn):
    names = ['foo', 'bar', 'baz']
    q2 = sql.SQL("insert into table ({0}) values ({1})").format(
            sql.SQL(', ').join(map(sql.Identifier, names)),
            sql.SQL(', ').join(map(sql.Placeholder, names)))
    result = q2.as_string(conn)
    assert (result ==
        'insert into table ("foo", "bar", "baz") '
        'values (%(foo)s, %(bar)s, %(baz)s)')