from LSP.plugin import ClientConfig
from LSP.plugin import uri_to_filename
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.edit import apply_workspace_edit
from LSP.plugin.core.edit import TextEditTuple
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.typing import Any, Callable, Dict, List, Mapping, Optional
from LSP.plugin.core.views import point_to_offset
from lsp_utils import NpmClientHandler
from lsp_utils import request_handler
import os
import sublime


def plugin_loaded():
    LspTypescriptPlugin.setup()


def plugin_unloaded():
    LspTypescriptPlugin.cleanup()


class LspTypescriptPlugin(NpmClientHandler):
    package_name = __package__
    server_directory = 'typescript-language-server'
    server_binary_path = os.path.join(server_directory, 'node_modules', 'typescript-language-server', 'lib', 'cli.js')

    @classmethod
    def is_allowed_to_start(
        cls,
        window: sublime.Window,
        initiating_view: Optional[sublime.View] = None,
        workspace_folders: Optional[List[WorkspaceFolder]] = None,
        configuration: Optional[ClientConfig] = None
    ) -> Optional[str]:
        if not workspace_folders:
            return 'This server only works when the window workspace includes some folders!'

    @request_handler('_typescript.rename')
    def on_typescript_rename(self, textDocumentPositionParams, respond):
        filename = uri_to_filename(textDocumentPositionParams['textDocument']['uri'])
        view = sublime.active_window().open_file(filename)

        if view:
            lsp_point = Point.from_lsp(textDocumentPositionParams['position'])
            point = point_to_offset(lsp_point, view)

            sel = view.sel()
            sel.clear()
            sel.add_all([point])
            view.run_command('lsp_symbol_rename')

        # Server doesn't require any specific response.
        respond(None)

    def on_pre_server_command(self, command: Mapping[str, Any], done_callback: Callable[[], None]) -> bool:
        if command['command'] == '_typescript.applyCompletionCodeAction':
            _, items = command['arguments']
            session = self.weaksession()
            if session:
                apply_workspace_edit(session.window, self._to_lsp_edits(items)).then(lambda _: done_callback())
                return True
        return False

    def _to_lsp_edits(self, items: Any) -> Dict[str, List[TextEditTuple]]:
        workspace_edits = {}  # type: Dict[str, List[TextEditTuple]]
        for item in items:
            for change in item['changes']:
                file_changes = []  # List[TextEditTuple]
                for text_change in change['textChanges']:
                    start = text_change['start']
                    end = text_change['end']
                    file_changes.append(
                        (
                            (start['line'] - 1, start['offset'] - 1),
                            (end['line'] - 1, end['offset'] - 1),
                            text_change['newText'],
                            None,
                        )
                    )
                    workspace_edits[change['fileName']] = file_changes
        return workspace_edits
