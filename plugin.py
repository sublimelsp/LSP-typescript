import os
import sublime
from LSP.plugin import ClientConfig
from LSP.plugin import uri_to_filename
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.types import List, Optional
from LSP.plugin.core.views import point_to_offset
from lsp_utils import NpmClientHandler
from lsp_utils import request_handler


def plugin_loaded():
    LspTypescriptPlugin.setup()


def plugin_unloaded():
    LspTypescriptPlugin.cleanup()


class LspTypescriptPlugin(NpmClientHandler):
    package_name = __package__
    server_directory = 'typescript-language-server'
    server_binary_path = os.path.join(
        server_directory, 'node_modules', 'typescript-language-server', 'lib', 'cli.js'
    )

    @classmethod
    def install_in_cache(cls) -> bool:
        return False

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
