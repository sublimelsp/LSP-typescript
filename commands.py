from __future__ import annotations

from LSP.plugin.execute_command import LspExecuteCommand
from LSP.plugin.locationpicker import LocationPicker
from LSP.protocol import Location
from LSP.protocol import LocationLink
from typing import Any

SESSION_NAME = str(__package__)


class LspTypescriptExecuteCommand(LspExecuteCommand):
    session_name = SESSION_NAME


class LspTypescriptGotoSourceDefinitionCommand(LspTypescriptExecuteCommand):

    def handle_success_async(self, result: list[Location] | list[LocationLink], command_name: str) -> None:
        window = self.view.window()
        if not result:
            if window:
                window.status_message('No source definitions found')
            return
        session = self.session_by_name()
        if not session:
            return
        if len(result) == 1:
            args: dict[str, Any] = {
                'location': result[0],
                'session_name': self.session_name,
            }
            if window:
                window.run_command('lsp_open_location', args)
        else:
            LocationPicker(self.view, session, result, side_by_side=False)
