import pytest
from newrelic.core.config import global_settings
from testing_support.fixtures import (validate_transaction_metrics,
        override_generic_settings, function_not_called,
        validate_transaction_event_attributes,
        validate_transaction_errors, override_ignore_status_codes,
        override_application_settings)
from testing_support.validators.validate_transaction_count import (
        validate_transaction_count)


@pytest.mark.parametrize('uri,name,metrics', (
    ('/native-simple', '_target_application:NativeSimpleHandler.get', None),
    ('/simple', '_target_application:SimpleHandler.get', None),
    ('/call-simple', '_target_application:CallSimpleHandler.get', None),
    ('/super-simple', '_target_application:SuperSimpleHandler.get', None),
    ('/coro', '_target_application:CoroHandler.get', None),
    ('/fake-coro', '_target_application:FakeCoroHandler.get', None),
    ('/coro-throw', '_target_application:CoroThrowHandler.get', None),
    ('/init', '_target_application:InitializeHandler.get', None),
    ('/multi-trace', '_target_application:MultiTraceHandler.get',
        [('Function/trace', 2)]),
))
@override_application_settings({'attributes.include': ['request.*']})
def test_server(app, uri, name, metrics):
    FRAMEWORK_METRIC = 'Python/Framework/Tornado/%s' % app.tornado_version
    METHOD_METRIC = 'Function/%s' % name

    metrics = metrics or []
    metrics.append((FRAMEWORK_METRIC, 1))
    metrics.append((METHOD_METRIC, 1))

    host = '127.0.0.1:' + str(app.get_http_port())

    @validate_transaction_metrics(
        name,
        rollup_metrics=metrics,
    )
    @validate_transaction_event_attributes(
        required_params={
            'agent': ('response.headers.contentType',),
            'user': (), 'intrinsic': ()},
        exact_attrs={
            'agent': {'request.headers.contentType': '1234',
                'request.headers.host': host,
                'request.method': 'GET',
                'request.uri': uri,
                'response.status': '200'},
            'user': {},
            'intrinsic': {'port': app.get_http_port()},
        },
    )
    def _test():
        response = app.fetch(uri, headers=(('Content-Type', '1234'),))
        assert response.code == 200

    _test()


@pytest.mark.parametrize('uri,name,metrics', (
    ('/native-simple', '_target_application:NativeSimpleHandler.get', None),
    ('/simple', '_target_application:SimpleHandler.get', None),
    ('/call-simple', '_target_application:CallSimpleHandler.get', None),
    ('/super-simple', '_target_application:SuperSimpleHandler.get', None),
    ('/coro', '_target_application:CoroHandler.get', None),
    ('/fake-coro', '_target_application:FakeCoroHandler.get', None),
    ('/coro-throw', '_target_application:CoroThrowHandler.get', None),
    ('/init', '_target_application:InitializeHandler.get', None),
    ('/ensure-future',
            '_target_application:EnsureFutureHandler.get',
        [('Function/trace', None)]),
    ('/multi-trace', '_target_application:MultiTraceHandler.get',
        [('Function/trace', 2)]),
))
def test_concurrent_inbound_requests(app, uri, name, metrics):
    from tornado import gen

    FRAMEWORK_METRIC = 'Python/Framework/Tornado/%s' % app.tornado_version
    METHOD_METRIC = 'Function/%s' % name

    metrics = metrics or []
    metrics.append((FRAMEWORK_METRIC, 1))
    metrics.append((METHOD_METRIC, 1))

    @validate_transaction_count(2)
    @validate_transaction_metrics(
        name,
        rollup_metrics=metrics,
    )
    def _test():
        url = app.get_url(uri)
        coros = (app.http_client.fetch(url) for _ in range(2))
        responses = app.io_loop.run_sync(lambda: gen.multi(coros))

        for response in responses:
            assert response.code == 200

    _test()


@validate_transaction_metrics('_target_application:CrashHandler.get')
@validate_transaction_errors(['builtins:ValueError'])
def test_exceptions_are_recorded(app):
    response = app.fetch('/crash')
    assert response.code == 500


@pytest.mark.parametrize('nr_enabled,ignore_status_codes', [
    (True, [405]),
    (True, []),
    (False, None),
])
def test_unsupported_method(app, nr_enabled, ignore_status_codes):

    def _test():
        response = app.fetch('/simple',
                method='TEAPOT', body=b'', allow_nonstandard_methods=True)
        assert response.code == 405

    if nr_enabled:
        _test = override_ignore_status_codes(ignore_status_codes)(_test)
        _test = validate_transaction_metrics(
                '_target_application:SimpleHandler')(_test)

        if ignore_status_codes:
            _test = validate_transaction_errors(errors=[])(_test)
        else:
            _test = validate_transaction_errors(
                    errors=['tornado.web:HTTPError'])(_test)
    else:
        settings = global_settings()
        _test = override_generic_settings(settings, {'enabled': False})(_test)

    _test()


@validate_transaction_errors(errors=[])
@validate_transaction_metrics('tornado.web:ErrorHandler')
@validate_transaction_event_attributes(
    required_params={'agent': (), 'user': (), 'intrinsic': ()},
    exact_attrs={
        'agent': {'request.uri': '/does-not-exist'},
        'user': {},
        'intrinsic': {},
    },
)
def test_not_found(app):
    response = app.fetch('/does-not-exist')
    assert response.code == 404


@override_generic_settings(global_settings(), {
    'enabled': False,
})
@function_not_called('newrelic.core.stats_engine',
        'StatsEngine.record_transaction')
def test_nr_disabled(app):
    response = app.fetch('/simple')
    assert response.code == 200


@pytest.mark.parametrize('uri,name', (
    ('/web-socket', '_target_application:WebSocketHandler'),
    ('/call-web-socket', '_target_application:WebNestedHandler'),
))
def test_web_socket(uri, name, app):
    import asyncio
    from tornado.websocket import websocket_connect

    @validate_transaction_metrics(
        name,
        rollup_metrics=[('Function/%s' % name, None)],
    )
    def _test():
        url = app.get_url(uri).replace('http', 'ws')

        @asyncio.coroutine
        def _connect():
            conn = yield from websocket_connect(url)
            return conn

        @validate_transaction_metrics(
            name,
        )
        def connect():
            return app.io_loop.run_sync(_connect)

        @function_not_called('newrelic.core.stats_engine',
                'StatsEngine.record_transaction')
        def call(call):
            @asyncio.coroutine
            def _call():
                yield from conn.write_message("test")
                resp = yield from conn.read_message()
                assert resp == "hello test"
            app.io_loop.run_sync(_call)

        conn = connect()
        call(conn)
        conn.close()

    _test()


LOOP_TIME_METRICS = (
    ('EventLoop/Wait/'
        'WebTransaction/Function/_target_application:BlockingHandler.get', 1),
)


@pytest.mark.parametrize('yield_before_finish', (True, False))
@validate_transaction_metrics(
    "_target_application:BlockingHandler.get",
    scoped_metrics=LOOP_TIME_METRICS,
)
def test_io_loop_blocking_time(app, yield_before_finish):
    from tornado import gen

    if yield_before_finish:
        url = app.get_url('/block-with-yield/2')
    else:
        url = app.get_url('/block/2')

    coros = (app.http_client.fetch(url) for _ in range(2))
    responses = app.io_loop.run_sync(lambda: gen.multi(coros))

    for response in responses:
        assert response.code == 200
