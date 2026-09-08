"""Resolve DNTLS names and publish this wallet's receive address."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional

from dntls_sdk.local import Client, FileCredentials, ProposeChangeRequest, RecordChange
from dntls_sdk.local.errors import LocalError
from dntls_sdk.portal.record_fields import RecordFields

from electrum import bitcoin
from electrum.plugin import BasePlugin, hook

if TYPE_CHECKING:
    from electrum.simple_config import SimpleConfig
    from electrum.wallet import Abstract_Wallet
    from dntls_sdk.local import Identity


def _client(
    config: Optional['SimpleConfig'] = None,
    on_register: Optional[Callable[[str], None]] = None,
) -> Client:
    """Return a Local Trust Resolver client."""
    if config is None:
        return Client()
    return Client(
        program='Electrum-LTC',
        credentials=FileCredentials(
            os.path.join(config.electrum_path(), 'dntls-resolver.token'),
        ),
        on_register=on_register,
    )


def merge_payment_addresses(current: Optional[Iterable[dict]], address: str) -> list[dict]:
    """Return payment_addresses with the litecoin entry set to address.

    Other networks keep their order. A litecoin entry is replaced in place;
    if none exists, one is appended.
    """
    replacement = {'network': 'litecoin', 'address': address}
    out: list[dict] = []
    replaced = False
    for item in current or ():
        if item.get('network') == 'litecoin':
            if not replaced:
                out.append(replacement)
                replaced = True
        else:
            out.append({'network': item['network'], 'address': item['address']})
    if not replaced:
        out.append(replacement)
    return out


def _litecoin_address_from_fields(fields: RecordFields) -> Optional[str]:
    """Return the litecoin payment address from fields, or None."""
    for item in fields.payment_addresses or ():
        if item.network == 'litecoin':
            return item.address
    return None


def _record_fields(body: bytes) -> RecordFields:
    """Parse resolver JSON bytes into typed record fields."""
    data = json.loads(body)
    record = data.get('record') or {}
    return RecordFields.from_dict(record.get('fields') or {})


class DntlsPlugin(BasePlugin):
    """Pay DNTLS names and publish a receive address through the resolver."""

    @hook
    def resolve_dntls(self, name: str) -> Optional[dict[str, Any]]:
        """Resolve name to a litecoin payment address via the Local Trust Resolver."""
        self.logger.info(f'consulting Local Trust Resolver for {name}')
        try:
            body = _client().resolve_record(name)
        except LocalError as exc:
            self.logger.info(f'Local Trust Resolver did not resolve {name}: {exc}')
            return None
        try:
            fields = _record_fields(body)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.logger.info(f'DNTLS record for {name} could not be read: {exc}')
            return None
        address = _litecoin_address_from_fields(fields)
        if not address or not bitcoin.is_address(address):
            return None
        return {
            'address': address,
            'name': name,
            'type': 'dntls',
        }

    def list_identities(self, on_register: Optional[Callable[[str], None]] = None) -> list[Identity]:
        """Return stored identities that can publish a record."""
        return [item for item in _client(self.config, on_register).identities() if item.has_private_identity]

    def publish_address(
        self,
        wallet: 'Abstract_Wallet',
        identity_name: str,
        fqdn: Optional[str] = None,
        on_register: Optional[Callable[[str], None]] = None,
    ) -> RecordChange:
        """Publish this wallet's receive address onto the named identity.

        identity_name is the store name passed to propose_change. fqdn is the
        published name used to read the current record; identity_name is used
        when fqdn is omitted.
        """
        address = wallet.get_unused_address()
        if not address:
            receiving = wallet.get_receiving_addresses()
            if not receiving:
                raise Exception('This wallet has no receive address.')
            address = receiving[0]
        record_name = fqdn or identity_name
        client = _client(self.config, on_register)
        fields = _record_fields(client.resolve_record(record_name))
        current = [item.to_dict() for item in (fields.payment_addresses or ())]
        replacement = merge_payment_addresses(current, address)
        return client.propose_change(
            ProposeChangeRequest(
                field='payment_addresses',
                replacement=replacement,
                reason="Publish this wallet's receive address",
                identity=identity_name,
            )
        )
