import celery

from newrelic.agent import (background_task, ignore_transaction,
        end_of_transaction)
from newrelic.packages import six

from testing_support.fixtures import validate_transaction_metrics
from tasks import app, add, tsum


def select_python_version(py2, py3):
    return six.PY3 and py3 or py2


@validate_transaction_metrics(
        name='test_celery:test_celery_task_as_function_trace',
        scoped_metrics=select_python_version(
                py2=[('Function/tasks:add.__call__', 1)],
                py3=[('Function/celery.app.task:Task.__call__', 1)]
        ),
        background_task=True)
@background_task()
def test_celery_task_as_function_trace():
    """
    Calling add() inside a transaction means the agent will record
    add() as a FunctionTrace.

    """
    result = add(3, 4)
    assert result == 7


@validate_transaction_metrics(
        name='tasks.add',
        group='Celery',
        scoped_metrics=[],
        background_task=True)
def test_celery_task_as_background_task():
    """
    Calling add() outside of a transaction means the agent will create
    a background transaction (with a group of 'Celery') and record add()
    as a background task.

    """
    result = add(3, 4)
    assert result == 7


@validate_transaction_metrics(
        name='test_celery:test_celery_tasks_multiple_function_traces',
        scoped_metrics=select_python_version(
                py2=[('Function/tasks:add.__call__', 1),
                     ('Function/tasks:tsum.__call__', 1)
                ],
                py3=[('Function/celery.app.task:Task.__call__', 2)]
        ),
        background_task=True)
@background_task()
def test_celery_tasks_multiple_function_traces():
    add_result = add(5, 6)
    assert add_result == 11

    tsum_result = tsum([1, 2, 3, 4])
    assert tsum_result == 10


@background_task()
def test_celery_tasks_ignore_transaction():
    """
    No transaction is recorded, due to the call to ignore_transaction(),
    so no validation fixture is used. The purpose of this test is to make
    sure the agent doesn't throw an error.

    """
    add_result = add(1, 2)
    assert add_result == 3

    ignore_transaction()

    tsum_result = tsum([1, 2, 3])
    assert tsum_result == 6


@validate_transaction_metrics(
        name='test_celery:test_celery_tasks_end_transaction',
        scoped_metrics=select_python_version(
                py2=[('Function/tasks:add.__call__', 1)],
                py3=[('Function/celery.app.task:Task.__call__', 1)]
        ),
        background_task=True)
@background_task()
def test_celery_tasks_end_transaction():
    """
    Only functions that run before the call to end_of_transaction() are
    included in the transaction.

    """
    add_result = add(1, 2)
    assert add_result == 3

    end_of_transaction()

    tsum_result = tsum([1, 2, 3])
    assert tsum_result == 6