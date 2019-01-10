import json
import os
import pytest
import sys
import tempfile

# NOTE: the test_utilization_settings_from_env_vars test mocks several of the
# methods in newrelic.core.data_collector and does not put them back!
from newrelic.core.data_collector import ApplicationSession
from newrelic.common.system_info import BootIdUtilization
from newrelic.common.utilization import (AWSUtilization,
        AzureUtilization, GCPUtilization)
from newrelic.common.object_wrapper import (transient_function_wrapper,
        function_wrapper)
import newrelic.core.config

try:
    # python 2.x
    reload
except NameError:
    # python 3.x
    from imp import reload

INITIAL_ENV = os.environ

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
FIXTURE = os.path.normpath(os.path.join(
        CURRENT_DIR, 'fixtures', 'utilization', 'utilization_json.json'))


def _load_tests():
    with open(FIXTURE, 'r') as fh:
        js = fh.read()
    return json.loads(js)


def _mock_logical_processor_count(cnt):
    def logical_processor_count():
        return cnt
    return logical_processor_count


def _mock_total_physical_memory(mem):
    def total_physical_memory():
        return mem
    return total_physical_memory


def _mock_gethostname(name):
    def gethostname(*args, **kwargs):
        return name
    return gethostname


def _mock_getips(ip_addresses):
    def getips(*args, **kwargs):
        return ip_addresses
    return getips


class UpdatedSettings(object):
    def __init__(self, test):
        self.test = test
        self.initial_settings = newrelic.core.config._settings

    def __enter__(self):
        """Update the settings dict to reflect the environment variables found in
        the test.

        """
        # clean settings cache and reload env vars
        # Note that reload can at times work in unexpected ways. All that is
        # required here is that the globals (such as
        # newrelic.core.config._settings) be reset.
        #
        # From python docs (2.x and 3.x)
        # "When a module is reloaded, its dictionary (containing the module's
        # global variables) is retained. Redefinitions of names will override
        # the old definitions, so this is generally not a problem."
        reload(newrelic.core.config)
        reload(newrelic.config)

        return newrelic.core.config.global_settings_dump()

    def __exit__(self, *args, **kwargs):
        newrelic.core.config._settings = self.initial_settings


def _get_effected_url_for_test(test):
    if test.get('input_aws_id'):
        return AWSUtilization.METADATA_URL
    elif test.get('input_azure_id'):
        return AzureUtilization.METADATA_URL
    elif test.get('input_gcp_id'):
        return GCPUtilization.METADATA_URL
    elif test.get('input_boot_id'):
        return BootIdUtilization.METADATA_URL


def _get_response_body_for_test(test):
    if test.get('input_aws_id'):
        return json.dumps({
            'instanceId': test.get('input_aws_id'),
            'instanceType': test.get('input_aws_type'),
            'availabilityZone': test.get('input_aws_zone'),
        }).encode('utf8')
    if test.get('input_azure_id'):
        return json.dumps({
            'location': test.get('input_azure_location'),
            'name': test.get('input_azure_name'),
            'vmId': test.get('input_azure_id'),
            'vmSize': test.get('input_azure_size'),
        }).encode('utf8')
    if test.get('input_gcp_id'):
        return json.dumps({
            'id': test.get('input_gcp_id'),
            'machineType': test.get('input_gcp_type'),
            'name': test.get('input_gcp_name'),
            'zone': test.get('input_gcp_zone'),
        }).encode('utf8')


class MockResponse(object):

    def __init__(self, code, body):
        self.code = code
        self.text = body

    def raise_for_status(self):
        assert str(self.code) == '200'

    def json(self):
        if hasattr(self.text, 'decode'):
            self.text = self.text.decode('utf-8')
        return json.loads(self.text)


def patch_Session_get(test):
    @transient_function_wrapper('newrelic.packages.requests', 'Session.get')
    def _patch_Session_get(wrapped, instance, args, kwargs):
        def _bind_params(url, *args, **kwargs):
            return url

        url = _bind_params(*args, **kwargs)
        effected_url = _get_effected_url_for_test(test)
        if url != effected_url:
            return MockResponse('500', 'Not the correct url, this is fine')

        body = _get_response_body_for_test(test)
        return MockResponse('200', body)
    return _patch_Session_get


def patch_boot_id_file(test):
    @function_wrapper
    def _patch_boot_id_file(wrapped, instance, args, kwargs):
        boot_id_file = None
        initial_sys_platform = sys.platform

        if test.get('input_boot_id'):
            boot_id_file = tempfile.NamedTemporaryFile()
            boot_id_file.write(test.get('input_boot_id'))
            boot_id_file.seek(0)
            BootIdUtilization.METADATA_URL = boot_id_file.name
            sys.platform = 'linux-mock-testing'  # ensure boot_id is gathered
        else:
            # do not gather boot_id at all, this will ensure there is nothing
            # extra in the gathered utilizations data
            sys.platform = 'not-linux'

        try:
            return wrapped(*args, **kwargs)
        finally:
            del boot_id_file  # close and thus delete the tempfile
            sys.platform = initial_sys_platform

    return _patch_boot_id_file


def patch_system_info(test):
    @function_wrapper
    def _patch_system_info(wrapped, instance, args, kwargs):
        dc = newrelic.core.data_collector
        initial_logical_processor_count = dc.logical_processor_count
        initial_total_physical_memory = dc.total_physical_memory
        initial_system_info_gethostname = dc.system_info.gethostname
        initial_system_info_getfqdn = dc.system_info.getfqdn
        initial_system_info_getips = dc.system_info.getips

        dc.logical_processor_count = _mock_logical_processor_count(
                test.get('input_logical_processors'))
        dc.total_physical_memory = _mock_total_physical_memory(
                test.get('input_total_ram_mib'))
        dc.system_info.gethostname = _mock_gethostname(
                test.get('input_hostname'))
        dc.system_info.getfqdn = _mock_gethostname(
                test.get('input_full_hostname'))
        dc.system_info.getips = _mock_getips(test.get('input_ip_address'))

        try:
            return wrapped(*args, **kwargs)
        finally:
            dc.logical_processor_count = initial_logical_processor_count
            dc.total_physical_memory = initial_total_physical_memory
            dc.system_info.gethostname = initial_system_info_gethostname
            dc.system_info.getfqdn = initial_system_info_getfqdn
            dc.system_info.getips = initial_system_info_getips

    return _patch_system_info


@pytest.mark.parametrize('test', _load_tests())
def test_utilization_settings(test, monkeypatch):

    env = test.get('input_environment_variables', {})

    if test.get('input_pcf_guid'):
        env.update({
            'CF_INSTANCE_GUID': test.get('input_pcf_guid'),
            'CF_INSTANCE_IP': test.get('input_pcf_ip'),
            'MEMORY_LIMIT': test.get('input_pcf_mem_limit'),
        })

    for key, val in env.items():
        monkeypatch.setenv(key, val)

    @patch_Session_get(test)
    @patch_boot_id_file(test)
    @patch_system_info(test)
    def _test_utilization_data():
        with UpdatedSettings(test) as settings:

            # Ignoring docker will ensure that there is nothing extra in the
            # gathered utilizations data
            settings['utilization.detect_docker'] = False

            local_config, = ApplicationSession._create_connect_payload(
                    '', [], [], settings)
            util_output = local_config['utilization']
            expected_output = test['expected_output_json']

            assert expected_output == util_output

    _test_utilization_data()
