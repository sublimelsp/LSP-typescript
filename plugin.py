from __future__ import annotations

from .plugin_types import ApplyRefactoringCommand
from .plugin_types import MoveToFileQuickPanelItem
from .plugin_types import MoveToFileQuickPanelItemId
from .plugin_types import ShowReferencesArguments
from .plugin_types import TypescriptPluginContribution
from .plugin_types import TypescriptVersionNotificationParams
from functools import partial
from LSP.plugin import ClientConfig
from LSP.plugin import notification_handler
from LSP.plugin import parse_uri
from LSP.plugin import Promise
from LSP.plugin import request_handler
from LSP.plugin import uri_from_view
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.protocol import Error
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.views import point_to_offset
from LSP.plugin.locationpicker import LocationPicker
from LSP.protocol import Location
from lsp_utils import NpmClientHandler
from pathlib import Path
from sublime_lib import ResourcePath
from typing import Any
from typing import Callable
from typing import cast
from typing import final
from typing import TYPE_CHECKING
from typing_extensions import override
import os
import sublime

if TYPE_CHECKING:
    from LSP.protocol import ConfigurationItem
    from LSP.protocol import ExecuteCommandParams
    from LSP.protocol import TextDocumentPositionParams


MOVE_TO_FILE_QUICK_PANEL_ITEMS: list[MoveToFileQuickPanelItem] = [
    {'id': MoveToFileQuickPanelItemId.ExistingFile, 'title':  'Select existing file...'},
    {'id': MoveToFileQuickPanelItemId.NewFile, 'title': 'Enter new file path...'},
]


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
        except ValueError:
            log(f'Failed parsing schema "{resource.file_path()}"')
            continue
        if not isinstance(contributed_plugins, list):
            log(f'Invalid contents of schema "{resource.file_path()}"')
            continue
        contributed_plugins = cast('list[TypescriptPluginContribution]', contributed_plugins)
        for plugin in contributed_plugins:
            name = plugin['name']
            location = cast('str', sublime.expand_variables(plugin['location'], variables))
            fullpath = Path(location) / name
            if not Path(fullpath).exists():
                log(f'Ignoring non-existent plugin at "{fullpath}"')
                continue
            contribution: TypescriptPluginContribution = {
                'name': name,
                'location': location,
            }
            if 'selector' in plugin:
                contribution['selector'] = plugin['selector']
            if 'languages' in plugin:
                contribution['languages'] = plugin['languages']
            plugins.append(contribution)
    return plugins


@final
class LspTypescriptPlugin(NpmClientHandler):
    package_name = str(__package__)
    server_directory = 'typescript-language-server'
    server_binary_path = str(Path(server_directory) / 'node_modules' / 'typescript-language-server' / 'lib' / 'cli.mjs')
    typescript_plugins: list[TypescriptPluginContribution] | None = None

    @classmethod
    @override
    def minimum_node_version(cls) -> tuple[int, int, int]:
        return (20, 0, 0)

    @classmethod
    @override
    def is_applicable(cls, view: sublime.View, config: ClientConfig) -> bool:
        if super().is_applicable(view, config):
            return True
        scheme, _ = parse_uri(uri_from_view(view))
        if scheme in config.schemes and (syntax := view.syntax()):
            for plugin in cls._get_typescript_plugins():
                if (selector := plugin.get('selector')) and sublime.score_selector(syntax.scope, selector) > 0:
                    return True
        return False

    @classmethod
    @override
    def on_pre_start(cls, window: sublime.Window, initiating_view: sublime.View,
                     workspace_folders: list[WorkspaceFolder], configuration: ClientConfig) -> str | None:
        plugins = configuration.initialization_options.get('plugins') or []
        for ts_plugin in cls._get_typescript_plugins():
            plugin: TypescriptPluginContribution = {
                'name': ts_plugin['name'],
                'location': ts_plugin['location'],
            }
            if 'languages' in ts_plugin:
                plugin['languages'] = ts_plugin['languages']
            plugins.append(plugin)
        configuration.initialization_options.set('plugins', plugins)
        return None

    @classmethod
    def _get_typescript_plugins(cls) -> list[TypescriptPluginContribution]:
        if cls.typescript_plugins is None:
            cls.typescript_plugins = find_typescript_plugin_contributions()
        return cls.typescript_plugins

    @request_handler('_typescript.rename')
    def on_typescript_rename(self, params: TextDocumentPositionParams) -> Promise[None]:
        _, filename = parse_uri(params['textDocument']['uri'])
        view = sublime.active_window().open_file(filename)
        if view:
            lsp_point = Point.from_lsp(params['position'])
            point = point_to_offset(lsp_point, view)
            sel = view.sel()
            sel.clear()
            sel.add_all([point])
            view.run_command('lsp_symbol_rename')
        # Server doesn't require any specific response.
        return Promise.resolve(None)

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

    @override
    def on_workspace_configuration(self, params: ConfigurationItem, configuration: Any) -> Any:
        if params.get('section') == 'formattingOptions' and (scope_uri := params.get('scopeUri')) \
                and (session := self.weaksession()) \
                and (buf := session.get_session_buffer_for_uri_async(scope_uri)) \
                and (session_view := next(iter(buf.session_views), None)):
            view_settings = session_view.view.settings()
            return {
                **(configuration if isinstance(configuration, dict) else {}),
                'tabSize': view_settings.get('tab_size'),
                'insertSpaces': view_settings.get('translate_tabs_to_spaces'),
            }
        return configuration

    @override
    def on_pre_server_command(self, command: ExecuteCommandParams, done_callback: Callable[[], None]) -> bool:
        command_name = command['command']
        if 'arguments' not in command:
            return False
        if command_name == 'editor.action.showReferences':
            _, __, references = cast('ShowReferencesArguments', cast('object', command['arguments']))
            self._handle_show_references(references)
            done_callback()
            return True
        if command_name == '_typescript.applyRefactoring':
            refactoring_command = cast('ApplyRefactoringCommand', cast('object', command))
            if self._handle_apply_refactoring(refactoring_command):
                done_callback()
                return True
        return False

    def _handle_show_references(self, references: list[Location]) -> None:
        session = self.weaksession()
        if not session:
            return
        view = session.window.active_view()
        if not view:
            return
        if len(references) == 1:
            args: dict[str, Any] = {
                'location': references[0],
                'session_name': session.config.name,
            }
            session.window.run_command('lsp_open_location', args)
        elif references:
            LocationPicker(view, session, references, side_by_side=False)
        else:
            sublime.status_message('No references found')

    def _handle_apply_refactoring(self, command: ApplyRefactoringCommand) -> bool:
        if command['arguments'][0]['action'] == 'Move to file':
            return self._handle_move_to_file(command)
        return False

    def _handle_move_to_file(self, command: ApplyRefactoringCommand) -> bool:
        argument = command['arguments'][0]
        if 'interactiveRefactorArguments' in argument:
            # Already augmented.
            return False
        session = self.weaksession()
        if not session:
            return True
        session.window.show_quick_panel([i['title'] for i in MOVE_TO_FILE_QUICK_PANEL_ITEMS],
                                        partial(self._on_move_file_action_select, command))
        return True

    def _on_move_file_action_select(self, command: ApplyRefactoringCommand, selected_index: int) -> None:
        if selected_index == -1:
            return
        session = self.weaksession()
        if not session:
            return
        item = MOVE_TO_FILE_QUICK_PANEL_ITEMS[selected_index]
        argument = command['arguments'][0]
        if item['id'] == MoveToFileQuickPanelItemId.ExistingFile:
            sublime.open_dialog(partial(self._on_file_selector_dialog_done, command), directory=argument['file'])
        elif item['id'] == MoveToFileQuickPanelItemId.NewFile:
            session.window.show_input_panel('New filename',
                                            str(Path(argument['file']).parent) + os.sep,
                                            on_done=lambda filepath: self._on_filepath_selected(filepath, command),
                                            on_change=None,
                                            on_cancel=self._on_no_file_selected)

    def _on_file_selector_dialog_done(self, command: ApplyRefactoringCommand, filename: str | list[str] | None) -> None:
        if isinstance(filename, str) and filename:
            self._on_filepath_selected(filename, command)
        else:
            self._on_no_file_selected()

    def _on_filepath_selected(self, filename: str, command: ApplyRefactoringCommand) -> None:
        if Path(filename).is_dir():
            sublime.status_message('Error: selected path is a directory')
            return
        self._execute_move_to_file_command(filename, command)

    def _on_no_file_selected(self) -> None:
        sublime.status_message('No file selected')

    def _execute_move_to_file_command(self, filename: str, command: ApplyRefactoringCommand) -> None:
        session = self.weaksession()
        if not session:
            return
        command['arguments'][0]['interactiveRefactorArguments'] = {
            'targetFile': filename
        }
        session.execute_command(cast('ExecuteCommandParams', command), progress=False, is_refactoring=True) \
            .then(self._handle_move_to_file_command_result)

    def _handle_move_to_file_command_result(self, result: Error | None) -> None:
        if isinstance(result, Error):
            sublime.status_message(str(result))
