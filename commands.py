from .protocol import Call, CallsDirection, CallsRequestParams, CallsResponse
from LSP.plugin import Request
from LSP.plugin import Session
from LSP.plugin.core.protocol import LocationLink
from LSP.plugin.core.registry import LspTextCommand
from LSP.plugin.core.typing import Optional
from LSP.plugin.core.views import text_document_position_params
from LSP.plugin.execute_command import LspExecuteCommand
from LSP.plugin.locationpicker import LocationPicker
import functools
import sublime


SESSION_NAME = "LSP-typescript"


class LspTypescriptOrganizeImportsCommand(LspExecuteCommand):
    session_name = SESSION_NAME


class LspTypescriptCallsCommand(LspTextCommand):
    session_name = SESSION_NAME

    def is_enabled(self) -> bool:
        selection = self.view.sel()
        return len(selection) > 0 and super().is_enabled()

    def run(self, edit: sublime.Edit, direction: CallsDirection) -> None:
        session = self.session_by_name(self.session_name)
        if session is None:
            return
        position_params = text_document_position_params(self.view, self.view.sel()[0].b)
        params = {
            'textDocument': position_params['textDocument'],
            'position': position_params['position'],
            'direction': direction
        }  # type: CallsRequestParams
        session.send_request(Request("textDocument/calls", params), functools.partial(self.on_result_async, session))

    def on_result_async(self, session: Session, result: Optional[CallsResponse]) -> None:
        if not result:
            return

        def to_location_link(call: Call) -> LocationLink:
            return {
                'targetUri': call['location']['uri'],
                'targetSelectionRange': call['location']['range'],
            }

        locations = list(map(to_location_link, result['calls']))
        self.view.run_command("add_jump_record", {"selection": [(r.a, r.b) for r in self.view.sel()]})
        LocationPicker(self.view, session, locations, side_by_side=False)
