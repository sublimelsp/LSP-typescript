from LSP.plugin import uri_to_filename
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.typing import Any, Callable
from LSP.plugin.core.views import point_to_offset
from lsp_utils import NpmClientHandler
from lsp_utils import request_handler
import os
import sublime


def plugin_loaded() -> None:
    LspTypescriptPlugin.setup()


def plugin_unloaded() -> None:
    LspTypescriptPlugin.cleanup()


class LspTypescriptPlugin(NpmClientHandler):
    package_name = __package__
    server_directory = 'typescript-language-server'
    server_binary_path = os.path.join(server_directory, 'node_modules', 'typescript-language-server', 'lib', 'cli.js')

    @request_handler('_typescript.rename')
    def on_typescript_rename(self, position_params: Any, respond: Callable[[None], None]) -> None:
        filename = uri_to_filename(position_params['textDocument']['uri'])
        view = sublime.active_window().open_file(filename)

        if view:
            lsp_point = Point.from_lsp(position_params['position'])
            point = point_to_offset(lsp_point, view)

            sel = view.sel()
            sel.clear()
            sel.add_all([point])
            view.run_command('lsp_symbol_rename')

        # Server doesn't require any specific response.
        respond(None)
