import threading

from newrelic.packages import six
from six.moves import http_client

from tornado_base_test import TornadoBaseTest

from _test_async_application import (ReturnFirstDivideRequestHandler,
        CallLaterRequestHandler, CancelAfterRanCallLaterRequestHandler,
        OneCallbackRequestHandler, PrepareReturnsFutureHandler,
        PrepareCoroutineReturnsFutureHandler,
        PrepareCoroutineFutureDoesNotResolveHandler,
        PrepareFinishesHandler, OnFinishWithGetCoroutineHandler,
        ThreadScheduledCallbackRequestHandler,
        CallbackOnThreadExecutorRequestHandler,
        ThreadScheduledCallAtRequestHandler,
        CallAtOnThreadExecutorRequestHandler, AddFutureRequestHandler,
        AddDoneCallbackRequestHandler, LastTimeoutFromThreadRequestHandler,
        SimpleThreadedFutureRequestHandler,
        BusyWaitThreadedFutureRequestHandler)

from tornado_fixtures import (
    tornado_validate_count_transaction_metrics,
    tornado_validate_time_transaction_metrics,
    tornado_validate_errors, tornado_validate_transaction_cache_empty)

def select_python_version(py2, py3):
    return six.PY3 and py3 or py2

class TornadoTest(TornadoBaseTest):

    # The count of 2 for the get method should be reduced to 1 after PYTHON-1851
    scoped_metrics = select_python_version(
            py2=[('Function/_test_async_application:'
                    'ReturnFirstDivideRequestHandler.do_divide', 1),
                ('Function/_test_async_application:do_divide (coroutine)', 1),
                ('Function/_test_async_application:'
                    'ReturnFirstDivideRequestHandler.get', 2),
                ('Function/_test_async_application:get (coroutine)', 1),],
            py3=[('Function/_test_async_application:'
                    'ReturnFirstDivideRequestHandler.do_divide', 1),
                ('Function/_test_async_application:ReturnFirstDivide'
                    'RequestHandler.do_divide (coroutine)', 1),
                ('Function/_test_async_application:'
                    'ReturnFirstDivideRequestHandler.get', 2),
                ('Function/_test_async_application:ReturnFirstDivide'
                    'RequestHandler.get (coroutine)', 1),])

    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors(errors=[])
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:ReturnFirstDivideRequestHandler.get',
            scoped_metrics=scoped_metrics)
    def test_nested_coroutines(self):
        response = self.fetch_response('/return-divide/100/10/')
        expected = ReturnFirstDivideRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'CallLaterRequestHandler.later', 1),
            ('Function/_test_async_application:'
                    'CallLaterRequestHandler.get', 1),
    ]

    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors(errors=[])
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:CallLaterRequestHandler.get',
            scoped_metrics=scoped_metrics)
    def test_call_at(self):
        response = self.fetch_response('/call-at')
        expected = CallLaterRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [('Function/_test_async_application:'
            'CallLaterRequestHandler.get', 1),]

    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors(errors=[])
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:CallLaterRequestHandler.get',
            scoped_metrics=scoped_metrics, forgone_metric_substrings=['later'])
    def test_cancel_call_at(self):
        response = self.fetch_response('/call-at/cancel')
        expected = CallLaterRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = select_python_version(
            py2=[('Function/_test_async_application:'
                    'CancelAfterRanCallLaterRequestHandler.later', 1),
                ('Function/_test_async_application:'
                    'CancelAfterRanCallLaterRequestHandler.get', 2),
                ('Function/_test_async_application:get (coroutine)', 1),],
            py3=[('Function/_test_async_application:'
                    'CancelAfterRanCallLaterRequestHandler.later', 1),
                ('Function/_test_async_application:'
                    'CancelAfterRanCallLaterRequestHandler.get', 2),
                ('Function/_test_async_application:CancelAfterRanCallLater'
                    'RequestHandler.get (coroutine)', 1),])

    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors(errors=[])
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:CancelAfterRanCallLaterRequestHandler.get',
            scoped_metrics=scoped_metrics)
    def test_cancel_call_at_after_callback_ran(self):
        response = self.fetch_response('/cancel-timer')
        expected = CancelAfterRanCallLaterRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [('Function/_test_async_application:'
            'OneCallbackRequestHandler.get', 1),
            ('Function/_test_async_application:'
            'OneCallbackRequestHandler.finish_callback', 1)]

    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:OneCallbackRequestHandler.get',
            scoped_metrics=scoped_metrics, transaction_count=2)
    def test_two_requests_on_the_same_connection(self):
        # This tests emulates the keep-alive behavior that chrome uses

        def make_streaming_requests(server):
            conn = http_client.HTTPConnection(server)

            conn.putrequest('GET', '/one-callback')
            conn.endheaders()
            resp = conn.getresponse()
            msg = resp.read()

            conn.putrequest('GET', '/one-callback')
            conn.endheaders()
            resp = conn.getresponse()
            msg = resp.read()

            self.assertEqual(msg, OneCallbackRequestHandler.RESPONSE)
            conn.close()
            self.io_loop.add_callback(self.stop)

        server = 'localhost:%s' % self.get_http_port()
        t = threading.Thread(target=make_streaming_requests, args=(server,))
        t.start()
        self.wait(timeout=5.0)
        t.join(10.0)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'PrepareReturnsFutureHandler.prepare', 1),
            ('Function/_test_async_application:'
                    'PrepareReturnsFutureHandler.get', 1),
            ('Function/_test_async_application:'
                    'PrepareReturnsFutureHandler.resolve_future', 1),
    ]

    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:PrepareReturnsFutureHandler.get',
            scoped_metrics=scoped_metrics)
    def test_prepare_returns_future(self):
        response = self.fetch_response('/prepare-future')
        expected = PrepareReturnsFutureHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = select_python_version(
            py2=[('Function/_test_async_application:'
                    'PrepareCoroutineReturnsFutureHandler.prepare', 2),
                ('Function/_test_async_application:prepare (coroutine)', 1),
                ('Function/_test_async_application:'
                    'PrepareCoroutineReturnsFutureHandler.get', 1),
                ('Function/_test_async_application:'
                    'PrepareCoroutineReturnsFutureHandler.resolve_future', 1)],
            py3=[('Function/_test_async_application:'
                    'PrepareCoroutineReturnsFutureHandler.prepare', 2),
                ('Function/_test_async_application:PrepareCoroutineReturns'
                    'FutureHandler.prepare (coroutine)', 1),
                ('Function/_test_async_application:'
                    'PrepareCoroutineReturnsFutureHandler.get', 1),
                ('Function/_test_async_application:'
                    'PrepareCoroutineReturnsFutureHandler.resolve_future', 1)])

    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:PrepareCoroutineReturnsFutureHandler.get',
            scoped_metrics=scoped_metrics)
    def test_prepare_coroutine(self):
        response = self.fetch_response('/prepare-coroutine')
        expected = PrepareCoroutineReturnsFutureHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'PrepareCoroutineFutureDoesNotResolveHandler.prepare', 2),
            ('Function/_test_async_application:'
                    'PrepareCoroutineFutureDoesNotResolveHandler.get', 1),
    ]

    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:PrepareCoroutine'
                    'FutureDoesNotResolveHandler.get',
            scoped_metrics=scoped_metrics)
    def test_prepare_coroutine_future_does_not_resolve(self):
        response = self.fetch_response('/prepare-unresolved')
        expected = PrepareCoroutineFutureDoesNotResolveHandler.RESPONSE
        self.assertEqual(response.body, expected)

    # get is never called if the request finishes in prepare
    scoped_metrics = [
            ('Function/_test_async_application:'
                    'PrepareFinishesHandler.prepare', 1),
    ]

    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:PrepareFinishesHandler.get',
            scoped_metrics=scoped_metrics)
    def test_prepare_with_finish(self):
        response = self.fetch_response('/prepare-finish')
        expected = PrepareFinishesHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'OnFinishWithGetCoroutineHandler.on_finish', 1),
            ('Function/_test_async_application:'
                    'OnFinishWithGetCoroutineHandler.get', 2),
    ]

    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:OnFinishWithGetCoroutineHandler.get',
            scoped_metrics=scoped_metrics)
    def test_on_finish_instrumented_with_coroutine_handler(self):
        # on_finish called from _execute that has yielded
        response = self.fetch_response('/on_finish-get-coroutine')
        expected = OnFinishWithGetCoroutineHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'ThreadScheduledCallbackRequestHandler.get', 1),
    ]
    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:ThreadScheduledCallbackRequestHandler.get',
            scoped_metrics=scoped_metrics,
            forgone_metric_substrings=['do_thing'])
    def test_thread_scheduled_callback(self):
        response = self.fetch_response('/thread-scheduled-callback')
        expected = ThreadScheduledCallbackRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    # Since the threaded callback is *scheduled* on the main thread, it
    # should still be included in the transaction
    scoped_metrics = [
            ('Function/_test_async_application:'
                    'CallbackOnThreadExecutorRequestHandler.get', 1),
            ('Function/_test_async_application:'
                    'CallbackOnThreadExecutorRequestHandler.do_thing', 1),
    ]
    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:CallbackOnThreadExecutorRequestHandler.get',
            scoped_metrics=scoped_metrics)
    def test_thread_ran_callback(self):
        response = self.fetch_response('/thread-ran-callback')
        expected = CallbackOnThreadExecutorRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'ThreadScheduledCallAtRequestHandler.get', 1),
    ]
    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:ThreadScheduledCallAtRequestHandler.get',
            scoped_metrics=scoped_metrics,
            forgone_metric_substrings=['do_thing'])
    def test_thread_scheduled_call_at(self):
        response = self.fetch_response('/thread-scheduled-call_at')
        expected = ThreadScheduledCallAtRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    # Since the threaded callback is *scheduled* on the main thread, it
    # should still be included in the transaction
    scoped_metrics = [
            ('Function/_test_async_application:'
                    'CallAtOnThreadExecutorRequestHandler.get', 1),
            ('Function/_test_async_application:'
                    'CallAtOnThreadExecutorRequestHandler.do_thing', 1),
    ]
    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:CallAtOnThreadExecutorRequestHandler.get',
            scoped_metrics=scoped_metrics)
    def test_thread_ran_call_at(self):
        response = self.fetch_response('/thread-ran-call_at')
        expected = CallAtOnThreadExecutorRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'AddFutureRequestHandler.get', 1),
            ('Function/_test_async_application:'
                    'AddFutureRequestHandler.do_thing', 1),
    ]
    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:AddFutureRequestHandler.get',
            scoped_metrics=scoped_metrics)
    def test_add_future(self):
        response = self.fetch_response('/add-future')
        expected = AddFutureRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'AddDoneCallbackRequestHandler.get', 1),
            ('Function/_test_async_application:'
                    'AddDoneCallbackRequestHandler.do_thing', 1),
    ]
    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:AddDoneCallbackRequestHandler.get',
            scoped_metrics=scoped_metrics)
    def test_add_done_callback(self):
        response = self.fetch_response('/add_done_callback')
        expected = AddDoneCallbackRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'LastTimeoutFromThreadRequestHandler.get', 1),
    ]
    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:LastTimeoutFromThreadRequestHandler.get',
            scoped_metrics=scoped_metrics)
    def test_last_timeout_removed_in_thread(self):
        response = self.fetch_response('/remove-last-timeout')
        expected = LastTimeoutFromThreadRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'SimpleThreadedFutureRequestHandler.get', 1),
    ]
    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:SimpleThreadedFutureRequestHandler.get',
            scoped_metrics=scoped_metrics,
            forgone_metric_substrings=['do_stuff'])
    def test_future_resolved_in_thread_add_done_callback(self):
        response = self.fetch_response('/future-thread')
        expected = SimpleThreadedFutureRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'SimpleThreadedFutureRequestHandler.get', 1),
    ]
    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:SimpleThreadedFutureRequestHandler.get',
            scoped_metrics=scoped_metrics,
            forgone_metric_substrings=['do_stuff'])
    def test_future_resolved_in_thread_add_future(self):
        response = self.fetch_response('/future-thread/add_future')
        expected = SimpleThreadedFutureRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'BusyWaitThreadedFutureRequestHandler.get', 1),
            ('Function/_test_async_application:'
                    'BusyWaitThreadedFutureRequestHandler.do_stuff', 1),
    ]
    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:BusyWaitThreadedFutureRequestHandler.get',
            scoped_metrics=scoped_metrics,
            forgone_metric_substrings=['long_wait'],
            )
    def test_future_resolved_in_thread_complex_add_done_callback(self):
        response = self.fetch_response('/future-thread-2')
        expected = BusyWaitThreadedFutureRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)

    scoped_metrics = [
            ('Function/_test_async_application:'
                    'BusyWaitThreadedFutureRequestHandler.get', 1),
            ('Function/_test_async_application:'
                    'BusyWaitThreadedFutureRequestHandler.do_stuff', 1),
            ('Function/_test_async_application:'
                    'BusyWaitThreadedFutureRequestHandler.long_wait', 1),
    ]
    @tornado_validate_transaction_cache_empty()
    @tornado_validate_errors()
    @tornado_validate_count_transaction_metrics(
            '_test_async_application:BusyWaitThreadedFutureRequestHandler.get',
            scoped_metrics=scoped_metrics)
    def test_future_resolved_in_thread_complex_add_future(self):
        response = self.fetch_response('/future-thread-2/add_future')
        expected = BusyWaitThreadedFutureRequestHandler.RESPONSE
        self.assertEqual(response.body, expected)
