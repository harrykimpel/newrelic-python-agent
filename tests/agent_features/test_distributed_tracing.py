import json
import pytest
import webtest
import copy

from newrelic.api.application import application_instance
from newrelic.api.background_task import background_task, BackgroundTask
from newrelic.api.transaction import current_transaction
from newrelic.api.web_transaction import wsgi_application, WebTransaction

from testing_support.fixtures import (override_application_settings,
        validate_attributes, validate_transaction_event_attributes,
        validate_error_event_attributes, validate_transaction_metrics)

distributed_trace_intrinsics = ['guid', 'nr.tripId', 'traceId', 'priority',
        'sampled']
inbound_payload_intrinsics = ['parent.type', 'parent.app', 'parent.account',
        'parent.transportType', 'parent.transportDuration', 'parentId']


payload = {
    'v': [0, 1],
    'd': {
        'ac': '1',
        'ap': '2827902',
        'id': '7d3efb1b173fecfa',
        'pa': '5e5733a911cfbc73',
        'pr': 10.001,
        'sa': True,
        'ti': 1518469636035,
        'tr': 'd6b4ba0c3a712ca',
        'ty': 'App',
    }
}
parent_order = ['parent_type', 'parent_account',
                'parent_app', 'parent_transport_type']
parent_info = {
    'parent_type': payload['d']['ty'],
    'parent_account': payload['d']['ac'],
    'parent_app': payload['d']['ap'],
    'parent_transport_type': 'HTTP'
}


@wsgi_application()
def target_wsgi_application(environ, start_response):
    status = '200 OK'
    output = b'hello world'
    response_headers = [('Content-type', 'text/html; charset=utf-8'),
                        ('Content-Length', str(len(output)))]

    txn = current_transaction()

    # Make assertions on the WebTransaction object
    assert txn.is_distributed_trace
    assert txn.parent_type == 'App'
    assert txn.parent_app == '2827902'
    assert txn.parent_account == '1'
    assert txn.parent_transport_type == 'HTTP'
    assert isinstance(txn.parent_transport_duration, float)
    assert txn._trace_id == 'd6b4ba0c3a712ca'
    assert txn.priority == 10.001
    assert txn.sampled
    assert txn.grandparent_id == '5e5733a911cfbc73'
    assert txn.parent_id == '7d3efb1b173fecfa'

    start_response(status, response_headers)
    return [output]


test_application = webtest.TestApp(target_wsgi_application)

_override_settings = {
    'trusted_account_ids': [1, 332029],
    'feature_flag': set(['distributed_tracing']),
}


@override_application_settings(_override_settings)
def test_distributed_tracing_web_transaction():
    headers = {'X-NewRelic-Trace': json.dumps(payload)}

    response = test_application.get('/', headers=headers)
    assert 'X-NewRelic-App-Data' not in response.headers


@pytest.mark.parametrize('accept_payload,has_grandparent', [
    (True, True),
    (True, False),
    (False, False),
])
def test_distributed_trace_attributes(accept_payload, has_grandparent):
    if accept_payload:
        _required_intrinsics = (
                distributed_trace_intrinsics + inbound_payload_intrinsics)
        _forgone_intrinsics = []
        _exact_attributes = {'agent': {}, 'user': {}, 'intrinsic': {
            'parent.type': 'Mobile',
            'parent.app': '2827902',
            'parent.account': '332029',
            'parent.transportType': 'HTTP',
            'parentId': '7d3efb1b173fecfa',
            'traceId': 'd6b4ba0c3a712ca',
        }}
        if has_grandparent:
            _required_intrinsics.append('grandparentId')
            _exact_attributes['grandparentId'] = '5e5733a911cfbc73'
        else:
            _forgone_intrinsics.append('grandparentId')

        _required_attributes = {
                'intrinsic': _required_intrinsics, 'agent': [], 'user': []}
        _forgone_attributes = {'intrinsic': [], 'agent': [], 'user': []}
    else:
        _required_intrinsics = distributed_trace_intrinsics
        _forgone_intrinsics = inbound_payload_intrinsics + ['grandparentId']

        _required_attributes = {
                'intrinsic': _required_intrinsics, 'agent': [], 'user': []}
        _forgone_attributes = {
                'intrinsic': _forgone_intrinsics, 'agent': [], 'user': []}
        _exact_attributes = None

    @override_application_settings(_override_settings)
    @validate_transaction_event_attributes(
            _required_attributes, _forgone_attributes, _exact_attributes)
    @validate_error_event_attributes(
            _required_attributes, _forgone_attributes, _exact_attributes)
    @validate_attributes('intrinsic',
            _required_intrinsics, _forgone_intrinsics)
    @background_task(name='test_distributed_trace_attributes')
    def _test():
        txn = current_transaction()

        payload = {
            "v": [0, 1],
            "d": {
                "ty": "Mobile",
                "ac": "332029",
                "ap": "2827902",
                "id": "7d3efb1b173fecfa",
                "tr": "d6b4ba0c3a712ca",
                "ti": 1518469636035
            }
        }
        if has_grandparent:
            payload['d']['pa'] = "5e5733a911cfbc73"

        if accept_payload:
            result = txn.accept_distributed_trace_payload(payload)
            assert result
        else:
            txn.create_distributed_tracing_payload()

        try:
            raise ValueError('cookies')
        except ValueError:
            txn.record_exception()

    _test()


_forgone_attributes = {
    'agent': [],
    'user': [],
    'intrinsic': (inbound_payload_intrinsics + ['grandparentId']),
}


@override_application_settings(_override_settings)
@validate_transaction_event_attributes(
        {}, _forgone_attributes)
@validate_error_event_attributes(
        {}, _forgone_attributes)
@validate_attributes('intrinsic',
        {}, _forgone_attributes['intrinsic'])
@background_task(name='test_distributed_trace_attrs_omitted')
def test_distributed_trace_attrs_omitted():
    txn = current_transaction()
    try:
        raise ValueError('cookies')
    except ValueError:
        txn.record_exception()


# test our distributed_trace metrics by creating a transaction and then forcing
# it to process a distributed trace payload
@pytest.mark.parametrize('web_transaction', (True, False))
@pytest.mark.parametrize('gen_error', (True, False))
@pytest.mark.parametrize('has_parent', (True, False))
def test_distributed_tracing_metrics(web_transaction, gen_error, has_parent):
    def _make_dt_tag(pi):
        return "%s/%s/%s/%s/all" % tuple(pi[x] for x in parent_order)

    # figure out which metrics we'll see based on the test params
    # note: we'll always see DurationByCaller if the distributed
    # tracing flag is turned on
    metrics = ['DurationByCaller']
    if gen_error:
        metrics.append('ErrorsByCaller')
    if has_parent:
        metrics.append('TransportDuration')

    tag = None
    dt_payload = copy.deepcopy(payload)

    # if has_parent is True, our metric name will be info about the parent,
    # otherwise it is Unknown/Unknown/Unknown/Unknown
    if has_parent:
        tag = _make_dt_tag(parent_info)
    else:
        tag = _make_dt_tag(dict((x, 'Unknown') for x in parent_info.keys()))
        del dt_payload['d']['id']

    # now run the test
    transaction_name = "test_dt_metrics_%s" % '_'.join(metrics)
    _rollup_metrics = [
        ("%s/%s%s" % (x, tag, bt), 1)
        for x in metrics
        for bt in ['', 'Web' if web_transaction else 'Other']
    ]

    def _make_test_transaction():
        application = application_instance()

        if not web_transaction:
            return BackgroundTask(application, transaction_name)

        environ = {'REQUEST_URI': '/trace_ends_after_txn'}
        tn = WebTransaction(application, environ)
        tn.set_transaction_name(transaction_name)
        return tn

    @override_application_settings(_override_settings)
    @validate_transaction_metrics(
        transaction_name,
        background_task=not(web_transaction),
        rollup_metrics=_rollup_metrics)
    def _test():
        with _make_test_transaction() as transaction:
            transaction.accept_distributed_trace_payload(dt_payload)

            if gen_error:
                try:
                    1 / 0
                except ZeroDivisionError:
                    transaction.record_exception()

    _test()