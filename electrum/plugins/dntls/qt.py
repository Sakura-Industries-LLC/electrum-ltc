"""Qt menu and dialogs for paying and publishing DNTLS names."""

from functools import partial
from typing import TYPE_CHECKING, Sequence

from dntls_sdk.local.errors import DeniedError, LocalError, UnverifiedError

from electrum.i18n import _
from electrum.plugin import hook
from electrum.util import ChoiceItem
from electrum.gui.qt.util import WaitingDialog

from .dntls import DntlsPlugin

if TYPE_CHECKING:
    from dntls_sdk.local import Identity, RecordChange
    from electrum.gui.qt.main_window import ElectrumWindow


class Plugin(DntlsPlugin):
    """Qt user interface for the DNTLS names plugin."""

    @hook
    def init_menubar(self, window: 'ElectrumWindow') -> None:
        """Add Tools → Publish address to DNTLS identity…"""
        window.tools_menu.addAction(
            _('Publish address to DNTLS identity…'),
            partial(self._publish_flow, window),
        )

    def _publish_flow(self, window: 'ElectrumWindow') -> None:
        """List identities, then publish after the user picks one."""
        WaitingDialog(
            window,
            _('The Local Trust Resolver is asking for permission to list your identities.'),
            self.list_identities,
            partial(self._on_identities, window),
            partial(self.done_processing_error, window),
        )

    def _on_identities(
        self,
        window: 'ElectrumWindow',
        identities: Sequence['Identity'],
    ) -> None:
        """Show a picker of FQDNs, then publish the receive address."""
        if not identities:
            window.show_error(_('No DNTLS identity is available on this machine.'))
            return
        active = next((item for item in identities if item.active), identities[0])
        choices = [ChoiceItem(key=item.name, label=item.fqdn) for item in identities]
        selected = window.query_choice(
            _('Choose a DNTLS identity'),
            choices,
            title=_('Publish address to DNTLS identity'),
            default_key=active.name,
        )
        if selected is None:
            return
        ident = next(item for item in identities if item.name == selected)
        WaitingDialog(
            window,
            _('Waiting for your approval in the Local Trust Resolver…'),
            lambda: self.publish_address(window.wallet, ident.name, fqdn=ident.fqdn),
            partial(self.done_processing_success, window),
            partial(self.done_processing_error, window),
        )

    def done_processing_success(
        self,
        window: 'ElectrumWindow',
        change: 'RecordChange',
    ) -> None:
        """Tell the user which address was published on which name."""
        address = ''
        if isinstance(change.value, list):
            for item in change.value:
                if isinstance(item, dict) and item.get('network') == 'litecoin':
                    address = item.get('address') or ''
                    break
        window.show_message(
            _('Published {address} on {name}.').format(
                address=address,
                name=change.identity,
            )
        )

    def done_processing_error(self, window: 'ElectrumWindow', exc_info) -> None:
        """Map resolver errors to short messages the user can act on."""
        exc = exc_info[1] if exc_info else None
        if isinstance(exc, DeniedError):
            window.show_error(_('You declined in the resolver.'))
        elif isinstance(exc, UnverifiedError):
            window.show_error(
                _('This build of the wallet is not attested; run it through the DNTLS launcher.')
            )
        elif isinstance(exc, LocalError) and exc.status_code is None:
            window.show_error(_('The Local Trust Resolver is not running.'))
        elif isinstance(exc, LocalError):
            window.show_error(str(exc))
        else:
            window.show_error(str(exc) if exc else _('Something went wrong.'))
