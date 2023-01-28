from .plugin_types import TypescriptVersionNotificationParams
from LSP.plugin import uri_to_filename
from LSP.plugin.core.protocol import Point, TextDocumentPositionParams
from LSP.plugin.core.typing import Callable, Dict, Tuple
from LSP.plugin.core.views import point_to_offset
from lsp_utils import notification_handler
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
    server_binary_path = os.path.join(server_directory, 'node_modules', 'typescript-language-server', 'lib', 'cli.mjs')

    @classmethod
    def minimum_node_version(cls) -> Tuple[int, int, int]:
        return (14, 16, 0)

    @request_handler('_typescript.rename')
    def on_typescript_rename(self, params: TextDocumentPositionParams, respond: Callable[[None], None]) -> None:
        filename = uri_to_filename(params['textDocument']['uri'])
        view = sublime.active_window().open_file(filename)
        if view:
            lsp_point = Point.from_lsp(params['position'])
            point = point_to_offset(lsp_point, view)
            sel = view.sel()
            sel.clear()
            sel.add_all([point])
            view.run_command('lsp_symbol_rename')
        # Server doesn't require any specific response.
        respond(None)

    @notification_handler('$/typescriptVersion')
    def on_typescript_version_async(self, params: TypescriptVersionNotificationParams) -> None:
        session = self.weaksession()
        if not session:
            return
        version_template = session.config.settings.get('settings.statusText')
        if not version_template or not isinstance(version_template, str):
            return
        status_text = version_template.replace('$version', params['version']).replace('$source', params['source'])
        if status_text:
            session.set_config_status_async(status_text)
