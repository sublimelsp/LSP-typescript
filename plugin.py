import os
import sublime
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.url import uri_to_filename
from LSP.plugin.core.views import point_to_offset
from lsp_utils import NpmClientHandler


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

    def on_ready(self, api) -> None:
        api.on_request('_typescript.rename', self._on_typescript_rename)

    def _on_typescript_rename(self, textDocumentPositionParams, respond):
        view = sublime.active_window().open_file(
            uri_to_filename(textDocumentPositionParams['textDocument']['uri'])
        )

        if view:
            lsp_point = Point.from_lsp(textDocumentPositionParams['position'])
            point = point_to_offset(lsp_point, view)

            sel = view.sel()
            sel.clear()
            sel.add_all([point])
            view.run_command('lsp_symbol_rename')

        # Server doesn't require any specific response.
        respond(None)
