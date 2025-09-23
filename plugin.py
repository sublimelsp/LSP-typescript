from __future__ import annotations
from .plugin_types import ApplyRefactoringCommand
from .plugin_types import MoveToFileQuickPanelItem
from .plugin_types import MoveToFileQuickPanelItemId
from .plugin_types import ShowReferencesCommand
from .plugin_types import TypescriptPluginContribution
from .plugin_types import TypescriptVersionNotificationParams
from functools import partial
from LSP.plugin import ClientConfig
from LSP.plugin import parse_uri
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.protocol import Error, Point, TextDocumentPositionParams, ExecuteCommandParams
from LSP.plugin.core.typing import cast, Callable, List, Optional, Tuple
from LSP.plugin.core.views import point_to_offset
from LSP.plugin.locationpicker import LocationPicker
from lsp_utils import notification_handler
from lsp_utils import NpmClientHandler
from lsp_utils import request_handler
from pathlib import Path
from sublime_lib import ResourcePath
import os
import sublime


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


class LspTypescriptPlugin(NpmClientHandler):
    package_name = __package__
    server_directory = 'typescript-language-server'
    server_binary_path = Path(server_directory) / 'node_modules' / 'typescript-language-server' / 'lib' / 'cli.mjs'
    typescript_plugins: list[TypescriptPluginContribution] | None = None

    @classmethod
    def minimum_node_version(cls) -> Tuple[int, int, int]:
        return (14, 16, 0)

    @classmethod
    def selector(cls, view: sublime.View, config: ClientConfig) -> str:
        plugins = cls._get_typescript_plugins()
        new_selector = config.selector
        for plugin in plugins:
            if "selector" in plugin:
                new_selector += f', {plugin["selector"]}'
        return new_selector

    @classmethod
    def on_pre_start(cls, window: sublime.Window, initiating_view: sublime.View,
                     workspace_folders: List[WorkspaceFolder], configuration: ClientConfig) -> Optional[str]:
        plugins = configuration.init_options.get('plugins') or []
        for ts_plugin in cls._get_typescript_plugins():
            plugin = {
                'name': ts_plugin['name'],
                'location': ts_plugin['location'],
            }
            if 'languages' in ts_plugin:
                plugin['languages'] = ts_plugin['languages']
            plugins.append(plugin)
        configuration.init_options.set('plugins', plugins)
        return None

    @classmethod
    def _get_typescript_plugins(cls) -> list[TypescriptPluginContribution]:
        if cls.typescript_plugins is None:
            cls.typescript_plugins = find_typescript_plugin_contributions()
        return cls.typescript_plugins

    @request_handler('_typescript.rename')
    def on_typescript_rename(self, params: TextDocumentPositionParams, respond: Callable[[None], None]) -> None:
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

    def on_pre_server_command(self, command: ExecuteCommandParams, done_callback: Callable[[], None]) -> bool:
        command_name = command['command']
        if command_name == 'editor.action.showReferences':
            references_command = cast(ShowReferencesCommand, command)
            self._handle_show_references(references_command)
            done_callback()
            return True
        if command_name == '_typescript.applyRefactoring':
            refactor_command = cast('ApplyRefactoringCommand', command)
            if self._handle_apply_refactoring(refactor_command):
                done_callback()
                return True
        return False

    def _handle_show_references(self, references_command: ShowReferencesCommand) -> None:
        session = self.weaksession()
        if not session:
            return
        view = session.window.active_view()
        if not view:
            return
        references = references_command['arguments'][2]
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

    def _handle_apply_refactoring(self, command: ApplyRefactoringCommand) -> bool:
        argument = command['arguments'][0]
        if argument['action'] == 'Move to file':
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
