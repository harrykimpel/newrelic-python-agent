from compat import basic_consume
import pika
import six

from newrelic.api.background_task import background_task
from newrelic.api.transaction import current_transaction
from newrelic.api.function_trace import FunctionTrace
from newrelic.common.encoding_utils import DistributedTracePayload

from testing_support.settings import rabbitmq_settings
from testing_support.fixtures import (override_application_settings,
        validate_transaction_metrics)

DB_SETTINGS = rabbitmq_settings()

_override_settings = {
    'primary_application_id': '3896659',
    'account_id': '332029',
    'trusted_account_key': '1',
    'cross_application_tracer.enabled': True,
    'distributed_tracing.enabled': True,
}

_test_distributed_tracing_basic_publish_metrics = [
    ('Supportability/TraceContext/Create/Success', 1),
    ('Supportability/DistributedTrace/CreatePayload/Success', 1),
    ('MessageBroker/RabbitMQ/Exchange/Produce/Named/Default', 1),
    ('DurationByCaller/Unknown/Unknown/Unknown/Unknown/all', 1),
    ('DurationByCaller/Unknown/Unknown/Unknown/Unknown/allOther', 1),
]


@validate_transaction_metrics(
        'test_distributed_tracing:do_basic_publish',
        rollup_metrics=_test_distributed_tracing_basic_publish_metrics,
        background_task=True)
@background_task()
def do_basic_publish(channel, QUEUE, properties=None):
    channel.basic_publish(
        exchange='',
        routing_key=QUEUE,
        body='Testing distributed_tracing 123',
        properties=properties,
    )


_test_distributed_tracing_basic_consume_rollup_metrics = [
    ('MessageBroker/RabbitMQ/Exchange/Produce/Named/Default', None),
    ('MessageBroker/RabbitMQ/Exchange/Consume/Named/Default', None),
    ('Supportability/DistributedTrace/AcceptPayload/Success', None),
    ('Supportability/TraceContext/Accept/Success', 1),
    ('DurationByCaller/App/332029/3896659/AMQP/all', 1),
    ('TransportDuration/App/332029/3896659/AMQP/all', 1),
    ('DurationByCaller/App/332029/3896659/AMQP/allOther', 1),
    ('TransportDuration/App/332029/3896659/AMQP/allOther', 1)

]

if six.PY3:
    _consume_txn_name = ('test_distributed_tracing:'
            'test_basic_consume_distributed_tracing_headers.'
            '<locals>.on_receive')
else:
    _consume_txn_name = (
        'test_distributed_tracing:on_receive')


@validate_transaction_metrics(
        _consume_txn_name,
        rollup_metrics=_test_distributed_tracing_basic_consume_rollup_metrics,
        background_task=True,
        group='Message/RabbitMQ/Exchange/Default')
def do_basic_consume(channel):
    channel.start_consuming()


@override_application_settings(_override_settings)
def test_basic_consume_distributed_tracing_headers():
    def on_receive(ch, method, properties, msg):
        headers = properties.headers
        assert headers
        assert 'NewRelicID' not in headers
        assert 'NewRelicTransaction' not in headers
        assert msg == b'Testing distributed_tracing 123'
        txn = current_transaction()

        assert txn
        assert txn._distributed_trace_state
        assert txn.parent_type == 'App'
        assert txn._trace_id.startswith(txn.parent_tx)
        assert txn.parent_span is not None
        assert txn.parent_account == txn.settings.account_id
        assert txn.parent_transport_type == 'AMQP'
        assert txn._priority is not None
        assert txn._sampled is not None

        ch.stop_consuming()

    with pika.BlockingConnection(
            pika.ConnectionParameters(DB_SETTINGS['host'])) as connection:
        channel = connection.channel()
        channel.queue_declare('TESTDT', durable=False)

        properties = pika.BasicProperties()
        properties.headers = {'Hello': 'World'}

        try:
            basic_consume(channel, 'TESTDT', on_receive, auto_ack=False)
            do_basic_publish(channel, 'TESTDT', properties=properties)
            do_basic_consume(channel)

        finally:
            channel.queue_delete('TESTDT')


_test_distributed_tracing_basic_get_metrics = [
    ('MessageBroker/RabbitMQ/Exchange/Produce/Named/Default', None),
    ('MessageBroker/RabbitMQ/Exchange/Consume/Named/Default', 1),
    ('DurationByCaller/Unknown/Unknown/Unknown/Unknown/all', 1),
    ('DurationByCaller/Unknown/Unknown/Unknown/Unknown/allOther', 1)
]


@validate_transaction_metrics(
        'test_distributed_tracing:do_basic_get',
        rollup_metrics=_test_distributed_tracing_basic_get_metrics,
        background_task=True)
@background_task()
def do_basic_get(channel, QUEUE):
    _, properties, msg = channel.basic_get(QUEUE)
    headers = properties.headers

    assert headers
    assert 'NewRelicID' not in headers
    assert 'NewRelicTransaction' not in headers
    assert msg == b'Testing distributed_tracing 123'

    txn = current_transaction()

    assert txn.client_cross_process_id is None
    assert txn.client_account_id is None
    assert txn.client_application_id is None


@override_application_settings(_override_settings)
def test_basic_get_no_distributed_tracing_headers():
    with pika.BlockingConnection(
            pika.ConnectionParameters(DB_SETTINGS['host'])) as connection:
        channel = connection.channel()
        channel.queue_declare('TESTDT', durable=False)

        properties = pika.BasicProperties()
        properties.headers = {'Hello': 'World'}

        try:
            do_basic_publish(channel, 'TESTDT', properties=properties)
            do_basic_get(channel, 'TESTDT')
        finally:
            channel.queue_delete('TESTDT')


@override_application_settings(_override_settings)
def test_distributed_tracing_sends_produce_id():
    with pika.BlockingConnection(
            pika.ConnectionParameters(DB_SETTINGS['host'])) as connection:
        channel = connection.channel()
        channel.queue_declare('TESTDT', durable=False)

        properties = pika.BasicProperties()
        properties.headers = {'Hello': 'World'}

        try:
            @background_task()
            def _publish():
                with FunctionTrace('foo') as trace:
                    channel.basic_publish(
                        exchange='',
                        routing_key='TESTDT',
                        body='Testing distributed_tracing 123',
                        properties=properties,
                    )

                return trace

            trace = _publish()

            raw_message = channel.basic_get('TESTDT')
        finally:
            channel.queue_delete('TESTDT')

        properties = raw_message[1]
        payload = DistributedTracePayload.from_http_safe(
                properties.headers["newrelic"])

        data = payload['d']

        # The payload should NOT contain the function trace ID
        assert data['id'] != trace.guid