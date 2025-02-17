from __future__ import annotations
from .plugin_types import TypescriptVersionNotificationParams
from LSP.plugin import ClientConfig
from LSP.plugin import Session
from LSP.plugin import uri_to_filename
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.protocol import Location, Point, TextDocumentPositionParams
from LSP.plugin.core.typing import Any, Callable, List, Mapping, Tuple
from LSP.plugin.core.views import point_to_offset
from LSP.plugin.locationpicker import LocationPicker
from lsp_utils import NodeRuntime
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

    @classmethod
    def on_pre_start(
        cls,
        window: sublime.Window,
        initiating_view: sublime.View,
        workspace_folders: list[WorkspaceFolder],
        configuration: ClientConfig,
    ) -> str | None:
        cls._support_vue_hybrid_mode(configuration)

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
        version_template = session.config.settings.get('statusText')
        if not version_template or not isinstance(version_template, str):
            return
        status_text = version_template.replace('$version', params['version']).replace('$source', params['source'])
        if status_text:
            session.set_config_status_async(status_text)

    def on_pre_server_command(self, command: Mapping[str, Any], done_callback: Callable[[], None]) -> bool:
        command_name = command['command']
        if command_name == 'editor.action.showReferences':
            session = self.weaksession()
            if not session:
                return False
            self._handle_show_references(session, command['arguments'][2])
            done_callback()
            return True
        return False

    def _handle_show_references(self, session: Session, references: List[Location]) -> None:
        view = session.window.active_view()
        if not view:
            return
        if len(references) == 1:
            args = {
                'location': references[0],
                'session_name': session.config.name,
            }
            session.window.run_command('lsp_open_location', args)
        elif references:
            LocationPicker(view, session, references, side_by_side=False)
        else:
            sublime.status_message('No references found')

    @classmethod
    def _support_vue_hybrid_mode(cls, configuration: ClientConfig) -> None:
        vue_settings = sublime.load_settings('LSP-vue.sublime-settings')
        if not vue_settings:
            return
        vue_hybrid_mode = vue_settings.get('initializationOptions', {}).get('vue.hybridMode', False)
        if not vue_hybrid_mode:
            return
        node_version = None
        node_runtime = NodeRuntime.get('LSP-vue', cls.storage_path(), '*')
        if node_runtime:
            node_version = str(node_runtime.resolve_version())
        if not node_version:
            return
        configuration.init_options.update({
            "plugins": [
                    {
                        "languages": ["vue"],
                        "location": os.path.join(cls._vue_package_storage_path(), node_version, 'server','node_modules'),
                        "name": "@vue/typescript-plugin",
                    }
            ],
        })
        configuration.selector = 'source.js, source.jsx, source.ts, source.tsx, text.html.vue'

    @classmethod
    def _vue_package_storage_path(cls) -> str:
        """
        The storage path for this package. Its path is '$DATA/Package Storage/[Package_Name]'.
        """
        return os.path.join(cls.storage_path(), 'LSP-vue')
