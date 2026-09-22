import os
import ssl
import unittest
from unittest.mock import Mock, patch, call
from urllib.error import URLError
import test_pages
from actionstack.soar import validate_ca,load_system_ca_bundles,Soar
from actionstack.core import Error

class TrustTests(unittest.TestCase):
    def test_linux_loads_os_bundle_in_addition_to_python_defaults(self):
        ctx=Mock()
        with patch('actionstack.soar.ssl.create_default_context',return_value=ctx),patch('actionstack.soar.sys.platform','linux'),patch.dict(os.environ,{},clear=True),patch('actionstack.soar.os.path.isfile',side_effect=lambda p:p=='/etc/pki/tls/certs/ca-bundle.crt'):
            self.assertIs(validate_ca('custom-pem'),ctx)
        ctx.load_verify_locations.assert_has_calls([call(cafile='/etc/pki/tls/certs/ca-bundle.crt'),call(cadata='custom-pem')])

    def test_explicit_ca_override_is_respected_and_unreadable_bundle_does_not_disable_validation(self):
        ctx=Mock()
        with patch('actionstack.soar.sys.platform','linux'),patch.dict(os.environ,{'SSL_CERT_FILE':'/explicit/bundle.pem'},clear=True):load_system_ca_bundles(ctx)
        ctx.load_verify_locations.assert_not_called()
        with patch('actionstack.soar.sys.platform','linux'),patch.dict(os.environ,{},clear=True),patch('actionstack.soar.os.path.isfile',return_value=True):
            ctx.load_verify_locations.side_effect=OSError('unreadable')
            load_system_ca_bundles(ctx)
        verified=validate_ca('')
        self.assertEqual(verified.verify_mode,ssl.CERT_REQUIRED);self.assertTrue(verified.check_hostname)

    def test_certificate_failure_is_distinguished_from_connection_timeout(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'secret-token')
        exc=ssl.SSLCertVerificationError(1,'certificate verify failed')
        exc.verify_message='hostname mismatch secret-token'
        for failure in [exc,URLError(exc)]:
            remote.opener=Mock();remote.opener.open.side_effect=failure
            with self.assertRaises(Error) as raised:remote.call('GET','container_options')
            self.assertEqual(raised.exception.status,502)
            self.assertIn('certificate verification failed',raised.exception.message)
            self.assertIn('hostname mismatch',raised.exception.message)
            self.assertNotIn('secret-token',raised.exception.message)
        remote.opener.open.side_effect=URLError(TimeoutError())
        with self.assertRaises(Error) as raised:remote.call('GET','container_options')
        self.assertEqual(raised.exception.status,504)
        self.assertNotIn('CA chain',raised.exception.message)

    def test_disabled_validation_does_not_load_trust_or_change_global_defaults(self):
        with patch('actionstack.soar.load_system_ca_bundles') as load:
            ctx=validate_ca('',True)
        load.assert_not_called();self.assertEqual(ctx.verify_mode,ssl.CERT_NONE)
        self.assertTrue(ssl.create_default_context().check_hostname)
