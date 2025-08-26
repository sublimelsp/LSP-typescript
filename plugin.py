from __future__ import annotations
from .plugin_types import TypescriptPluginContribution
from .plugin_types import TypescriptVersionNotificationParams
from LSP.plugin import ClientConfig
from LSP.plugin import Session
from LSP.plugin import uri_to_filename
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.protocol import Location, Point, TextDocumentPositionParams
from LSP.plugin.core.typing import cast, Any, Callable, List, Mapping, Tuple
from LSP.plugin.core.views import point_to_offset
from LSP.plugin.locationpicker import LocationPicker
from lsp_utils import notification_handler
from lsp_utils import NpmClientHandler
from lsp_utils import request_handler
from sublime_lib import ResourcePath
import os
import sublime


def log(message: str) -> None:
    print(f'[{__package__}] {message}')


def plugin_loaded() -> None:
    LspTypescriptPlugin.setup()


def plugin_unloaded() -> None:
    LspTypescriptPlugin.cleanup()
    LspTypescriptPlugin.typescript_plugins = None


def find_typescript_plugin_contributions() -> list[TypescriptPluginContribution]:
    variables = {'storage_path': LspTypescriptPlugin.storage_path()}
    resources = ResourcePath.glob_resources('typescript-plugins.json')
    plugins: list[TypescriptPluginContribution] = []
    for resource in resources:
        try:
            contributed_plugins = sublime.decode_value(resource.read_text())
        except Exception:
            log(f'Failed parsing schema "{resource.file_path()}"')
            continue
        if not isinstance(contributed_plugins, list):
            log(f'Invalid contents of schema "{resource.file_path()}"')
            continue
        contributed_plugins = cast('list[TypescriptPluginContribution]', contributed_plugins)
        for plugin in contributed_plugins:
            name = plugin['name']
            location = cast('str', sublime.expand_variables(plugin['location'], variables))
            fullpath = os.path.join(location, name)
            if not os.path.exists(fullpath):
                log(f'Ignoring non-existant plugin at "{fullpath}"')
                continue
            plugins.append({
                'name': name,
                'languages': plugin['languages'],
                'location': location,
                'selector': plugin['selector']
            })
    return plugins


class LspTypescriptPlugin(NpmClientHandler):
    package_name = __package__
    server_directory = 'typescript-language-server'
    server_binary_path = os.path.join(server_directory, 'node_modules', 'typescript-language-server', 'lib', 'cli.mjs')
    typescript_plugins: list[TypescriptPluginContribution] | None = None

    @classmethod
    def minimum_node_version(cls) -> Tuple[int, int, int]:
        return (14, 16, 0)

    @classmethod
    def on_configuration_loaded(cls, window: sublime.Window, workspace_folders: list[WorkspaceFolder],
                                configuration: ClientConfig) -> None:
        cls._handle_typescript_plugins(configuration)

    @classmethod
    def _handle_typescript_plugins(cls, configuration: ClientConfig) -> None:
        if cls.typescript_plugins is None:
            cls.typescript_plugins = find_typescript_plugin_contributions()
        plugins = configuration.init_options.get('plugins') or []
        for plugin in cls.typescript_plugins:
            plugins.append({
                'name': plugin['name'],
                'languages': plugin['languages'],
                'location': plugin['location'],
            })
            configuration.selector += f', {plugin["selector"]}'
        configuration.init_options.set('plugins', plugins)

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
