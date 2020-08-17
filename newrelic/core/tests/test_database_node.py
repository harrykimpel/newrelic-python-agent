import pytest
import newrelic.core.database_node
from newrelic.common import system_info
from newrelic.core.config import finalize_application_settings

HOST = 'cookiemonster'

_backup_methods = {}


def setup_module(module):

    # Mock out the calls used to create the connect payload.
    def gethostname():
        return HOST
    _backup_methods['gethostname'] = system_info.gethostname
    system_info.gethostname = gethostname


def teardown_module(module):
    system_info.gethostname = _backup_methods['gethostname']


_db_node = newrelic.core.database_node.DatabaseNode(
        dbapi2_module=None,
        sql='COMMIT',
        children=[],
        start_time=0.1,
        end_time=0.9,
        duration=0.8,
        exclusive=0.8,
        stack_trace=[],
        sql_format='obfuscated',
        connect_params=((), {'host': 'localhost', 'port': 1234}),
        cursor_params=None,
        sql_parameters=None,
        execute_params=None,
        host='localhost',
        port_path_or_id='1234',
        database_name='bar',
        guid=None,
        agent_attributes={},
        user_attributes={},
)


@pytest.fixture(autouse=True)
def cleanup_caches():
    for attr in ('_db_instance',):
        if hasattr(_db_node, attr):
            delattr(_db_node, attr)


def test_product_property():
    assert _db_node.product is None


def test_operation():
    assert _db_node.operation == 'commit'


def test_target():
    assert _db_node.target == ''


def test_formatted():
    assert _db_node.formatted == 'COMMIT'


def test_instance_hostname():
    assert _db_node.instance_hostname == HOST


def test_span_event():
    span_event = _db_node.span_event(finalize_application_settings())
    a_attrs = span_event[2]

    # Verify that all hostnames have been converted to instance_hostname

    host, port = a_attrs['peer.address'].split(':')
    assert host == HOST
    assert port == '1234'

    assert a_attrs['peer.hostname'] == HOST


def test_db_instance_cache():
    _db_node._db_instance = 'FOO'
    assert _db_node.db_instance == 'FOO'


def test_db_instance():
    assert _db_node.db_instance == 'bar'