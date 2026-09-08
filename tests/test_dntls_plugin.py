import json
import os
from unittest.mock import patch

from dntls_sdk.local.client import CODE_ALPHABET, CODE_LENGTH, new_code
from dntls_sdk.local.errors import LocalError

from electrum.plugins.dntls.dntls import DntlsPlugin, merge_payment_addresses, _client
from electrum.simple_config import SimpleConfig

from . import ElectrumTestCase

TESTNET_ADDRESS = 'myNNuLYNgHE92nGQuJd5mXo6gy9gKXEDyQ'


def _record_body(fields: dict) -> bytes:
    """Return resolver JSON bytes for a record with the given fields."""
    return json.dumps({
        'root_hash': 'AA==',
        'record': {
            'service_key': 'AQ==',
            'fields': fields,
        },
    }).encode()


class _StubClient:
    """Resolver client that returns a fixed body or raises."""

    def __init__(self, body=None, error=None):
        """Store the fixture body or error for resolve_record."""
        self.body = body
        self.error = error

    def resolve_record(self, name):
        """Return the fixture body, or raise the stored error."""
        if self.error is not None:
            raise self.error
        return self.body


class TestDntlsPlugin(ElectrumTestCase):
    TESTNET = True

    def setUp(self):
        super().setUp()
        self.config = SimpleConfig({
            'electrum_path': self.electrum_path,
            'testnet': True,
        })
        self.plugin = DntlsPlugin(None, self.config, 'dntls')

    def test_merge_replaces_litecoin_entry(self):
        current = [
            {'network': 'litecoin', 'address': 'old'},
            {'network': 'other', 'address': 'keep'},
        ]
        self.assertEqual(
            [
                {'network': 'litecoin', 'address': TESTNET_ADDRESS},
                {'network': 'other', 'address': 'keep'},
            ],
            merge_payment_addresses(current, TESTNET_ADDRESS),
        )

    def test_merge_appends_when_missing(self):
        current = [{'network': 'other', 'address': 'keep'}]
        self.assertEqual(
            [
                {'network': 'other', 'address': 'keep'},
                {'network': 'litecoin', 'address': TESTNET_ADDRESS},
            ],
            merge_payment_addresses(current, TESTNET_ADDRESS),
        )

    def test_merge_preserves_order(self):
        current = [
            {'network': 'aaa', 'address': '1'},
            {'network': 'litecoin', 'address': 'old'},
            {'network': 'zzz', 'address': '2'},
        ]
        self.assertEqual(
            [
                {'network': 'aaa', 'address': '1'},
                {'network': 'litecoin', 'address': TESTNET_ADDRESS},
                {'network': 'zzz', 'address': '2'},
            ],
            merge_payment_addresses(current, TESTNET_ADDRESS),
        )

    def test_resolve_dntls_returns_testnet_address(self):
        body = _record_body({
            'payment_addresses': [
                {'network': 'other', 'address': 'ignore'},
                {'network': 'litecoin', 'address': TESTNET_ADDRESS},
            ],
        })
        stub = _StubClient(body=body)
        with patch('electrum.plugins.dntls.dntls._client', return_value=stub):
            result = self.plugin.resolve_dntls('whoami.dntls')
        self.assertEqual(
            {
                'address': TESTNET_ADDRESS,
                'name': 'whoami.dntls',
                'type': 'dntls',
            },
            result,
        )

    def test_resolve_dntls_missing_field_returns_none(self):
        stub = _StubClient(body=_record_body({}))
        with patch('electrum.plugins.dntls.dntls._client', return_value=stub):
            self.assertIsNone(self.plugin.resolve_dntls('whoami.dntls'))

    def test_resolve_dntls_resolver_unavailable_returns_none(self):
        stub = _StubClient(error=LocalError('local: request /v1/resolve'))
        with patch('electrum.plugins.dntls.dntls._client', return_value=stub):
            self.assertIsNone(self.plugin.resolve_dntls('whoami.dntls'))

    def test_registering_client_credential_path_under_electrum_path(self):
        captured = {}

        class StubClient:
            def __init__(self, *args, **kwargs):
                captured.update(kwargs)

        with patch('electrum.plugins.dntls.dntls.Client', StubClient):
            _client(self.config, on_register=lambda code: None)
        path = os.fspath(captured['credentials'].path)
        electrum_path = self.config.electrum_path()
        self.assertTrue(path.startswith(electrum_path + os.sep))
        self.assertEqual('dntls-resolver.token', os.path.basename(path))

    def test_on_register_receives_confirmation_code(self):
        seen = []

        class StubClient:
            def __init__(self, *args, **kwargs):
                on_register = kwargs.get('on_register')
                if on_register is not None:
                    on_register(new_code())

        with patch('electrum.plugins.dntls.dntls.Client', StubClient):
            _client(self.config, on_register=seen.append)
        self.assertEqual(1, len(seen))
        code = seen[0]
        self.assertEqual(CODE_LENGTH, len(code))
        self.assertTrue(all(ch in CODE_ALPHABET for ch in code))
