import unittest
import logging

import newrelic.core.agent

import newrelic.api.settings

import newrelic.api.transaction

import newrelic.api.web_transaction

import newrelic.agent

_logger = logging.getLogger('newrelic')

# Hardwire settings for test script rather than agent configuration file
# as is easier to work with in test script. We override transaction and
# database trace thresholds so everything is collected. To the extent
# that the old logging system is still used in the code, possibly
# nothing at this point, anything will end up in log file in same
# directory as this script where name is this files name with '.log'
# appended.

settings = newrelic.api.settings.settings()

settings.host = 'staging-collector.newrelic.com'
settings.port = 80
settings.license_key = '84325f47e9dec80613e262be4236088a9983d501'

settings.app_name = 'Python Agent Test'

settings.log_file = '%s.log' % __file__
settings.log_level = logging.DEBUG

settings.transaction_tracer.transaction_threshold = 0
settings.transaction_tracer.stack_trace_threshold = 0

# app key and secret from the Dropbox developer website
APP_KEY = 'uiu6m0nfbp84adi'
APP_SECRET = '3m25zc1npmcec7w'
ACCESS_TYPE = 'app_folder'  # should be 'dropbox' or 'app_folder' as configured for your app

# The WSGI application and test to be done.

@newrelic.api.web_transaction.wsgi_application()
def handler(environ, start_response):
    status = '200 OK'
    output = 'Hello World!'

    from dropbox import client, session, rest

    sess = session.DropboxSession(APP_KEY, APP_SECRET, ACCESS_TYPE)

    request_token = sess.obtain_request_token()

    # This will fail if the user didn't visit the above URL and hit 'Allow'
    try:
        access_token = sess.obtain_access_token(request_token)
    except rest.ErrorResponse, e:
        # Make the user sign in and authorize this token
        print "Error:", e
        url = sess.build_authorize_url(request_token)
        print "url:", url
        print "Please authorize in the browser."
        raw_input()
        access_token = sess.obtain_access_token(request_token)

    client = client.DropboxClient(sess)
    print "linked account:", client.account_info()

    f = open('working-draft.txt')
    response = client.put_file('/magnum-opus.txt', f)
    print "uploaded:", response

    response_headers = [('Content-type', 'text/plain'),
                        ('Content-Length', str(len(output)))]
    start_response(status, response_headers)

    return [output]

class TransactionTests(unittest.TestCase):

    # Note that you can only have a single test in this file
    # as code makes assumption that test is first to run and
    # nothing has been run before.

    def setUp(self):
        _logger.debug('STARTING - %s' % self._testMethodName)

    def tearDown(self):
        _logger.debug('STOPPING - %s' % self._testMethodName)

    def test_transaction(self):

        # Initialise higher level instrumentation layers. Not
        # that they will be used in this test for now.

        newrelic.agent.initialize()

        # Want to force agent initialisation and connection so
        # we know that data will actually get through to core
        # and not lost because application not activated.

        agent = newrelic.core.agent.agent_instance()

        name = settings.app_name
        application_settings = agent.application_settings(name)
        self.assertEqual(application_settings, None)

        agent.activate_application(name, timeout=5.0)
        application_settings = agent.application_settings(name)

        # If this fails it means we weren't able to establish
        # a connection and activate the named application.

        self.assertNotEqual(application_settings, None)

        def start_response(status, headers): pass

        environ = {'REQUEST_URI': '/dropbox'}
        handler(environ, start_response).close()

if __name__ == '__main__':
    unittest.main()