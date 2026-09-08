"""Qt menu and dialogs for paying and publishing DNTLS names."""

from functools import partial
from typing import TYPE_CHECKING, Callable, Optional, Sequence

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout

from dntls_sdk.local.errors import DeniedError, LocalError, UnregisteredError

from electrum.i18n import _
from electrum.plugin import hook
from electrum.util import ChoiceItem
from electrum.gui.qt.util import (
    Buttons,
    CancelButton,
    MONOSPACE_FONT,
    WaitingDialog,
    WWLabel,
)

from .dntls import DntlsPlugin

if TYPE_CHECKING:
    from dntls_sdk.local import Identity, RecordChange
    from electrum.gui.qt.main_window import ElectrumWindow


class _RegisterPrompt(QObject):
    """Show the registration confirmation code on the GUI thread."""

    _show_code = pyqtSignal(str)
    _finished = pyqtSignal()

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._dialog: Optional[QDialog] = None
        self._show_code.connect(self._open_dialog)
        self._finished.connect(self._close_dialog)

    def on_register(self, code: str) -> None:
        """Queue the confirmation-code dialog; returns immediately."""
        self._show_code.emit(code)

    def finish(self) -> None:
        """Close the confirmation-code dialog when the pending call ends."""
        self._finished.emit()

    def _open_dialog(self, code: str) -> None:
        parent = self.parent()
        dialog = QDialog(parent)
        dialog.setWindowTitle(_('Register with the Local Trust Resolver'))
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        vbox = QVBoxLayout(dialog)
        code_label = QLabel(code)
        font = QFont(MONOSPACE_FONT)
        font.setPointSize(24)
        code_label.setFont(font)
        code_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        code_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        vbox.addWidget(code_label)
        vbox.addWidget(WWLabel(_(
            'The resolver is asking whether Electrum-LTC may register. '
            'Allow it only if the resolver shows this exact code.'
        )))
        vbox.addLayout(Buttons(CancelButton(dialog)))
        dialog.show()
        dialog.raise_()
        self._dialog = dialog

    def _close_dialog(self) -> None:
        dialog = self._dialog
        self._dialog = None
        if dialog is not None:
            dialog.close()


class Plugin(DntlsPlugin):
    """Qt user interface for the DNTLS names plugin."""

    @hook
    def init_menubar(self, window: 'ElectrumWindow') -> None:
        """Add Tools → Publish address to DNTLS identity…"""
        window.tools_menu.addAction(
            _('Publish address to DNTLS identity…'),
            partial(self._publish_flow, window),
        )

    def _with_register_prompt(
        self,
        window: 'ElectrumWindow',
        work: Callable,
    ):
        prompt = _RegisterPrompt(window)

        def task():
            try:
                return work(prompt.on_register)
            finally:
                prompt.finish()

        return task

    def _publish_flow(self, window: 'ElectrumWindow') -> None:
        """List identities, then publish after the user picks one."""
        WaitingDialog(
            window,
            _('The Local Trust Resolver is asking for permission to list your identities.'),
            self._with_register_prompt(
                window,
                lambda on_register: self.list_identities(on_register=on_register),
            ),
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
            self._with_register_prompt(
                window,
                lambda on_register: self.publish_address(
                    window.wallet,
                    ident.name,
                    fqdn=ident.fqdn,
                    on_register=on_register,
                ),
            ),
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
        elif isinstance(exc, UnregisteredError):
            window.show_error(_(
                'Electrum-LTC is not registered with the Local Trust Resolver. '
                'Try again and allow the registration.'
            ))
        elif isinstance(exc, LocalError) and exc.status_code is None:
            window.show_error(_('The Local Trust Resolver is not running.'))
        elif isinstance(exc, LocalError):
            window.show_error(str(exc))
        else:
            window.show_error(str(exc) if exc else _('Something went wrong.'))
