from __future__ import annotations

from .plugin_types import ApplyRefactoringArgument
from .plugin_types import MoveToFileQuickPanelItem
from .plugin_types import MoveToFileQuickPanelItemId
from .plugin_types import TypescriptPluginContribution
from .plugin_types import TypescriptVersionNotificationParams
from functools import partial
from LSP.plugin import ClientResponse
from LSP.plugin import command_handler
from LSP.plugin import Error
from LSP.plugin import IsApplicableContext
from LSP.plugin import LspPlugin
from LSP.plugin import notification_handler
from LSP.plugin import OnPreStartContext
from LSP.plugin import parse_uri
from LSP.plugin import Promise
from LSP.plugin import Request
from LSP.plugin import request_handler
from LSP.plugin import Session
from LSP.plugin import ST_STORAGE_PATH
from LSP.plugin import uri_from_view
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.views import point_to_offset
from LSP.protocol import ExecuteCommandParams
from LSP.protocol import LSPAny
from lsp_utils import NodeManager
from pathlib import Path
from sublime_lib import ResourcePath
from typing import cast
from typing import final
from typing import TYPE_CHECKING
from typing_extensions import override
import os
import sublime

if TYPE_CHECKING:
    from LSP.protocol import TextDocumentPositionParams


MOVE_TO_FILE_QUICK_PANEL_ITEMS: list[MoveToFileQuickPanelItem] = [
    {'id': MoveToFileQuickPanelItemId.ExistingFile, 'title':  'Select existing file...'},
    {'id': MoveToFileQuickPanelItemId.NewFile, 'title': 'Enter new file path...'},
]


def log(message: str) -> None:
    print(f'[{__package__}] {message}')


def find_typescript_plugin_contributions() -> list[TypescriptPluginContribution]:
    variables = {'storage_path': ST_STORAGE_PATH}
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
class LspTypescriptPlugin(LspPlugin):
    typescript_plugins: list[TypescriptPluginContribution] | None = None

    @classmethod
    @override
    def is_applicable_async(cls, context: IsApplicableContext) -> bool:
        if super().is_applicable_async(context):
            return True
        scheme, _ = parse_uri(uri_from_view(context.view))
        if scheme in context.configuration.schemes and (syntax := context.view.syntax()):
            for plugin in cls._get_typescript_plugins():
                if (selector := plugin.get('selector')) and sublime.score_selector(syntax.scope, selector) > 0:
                    return True
        return False

    @classmethod
    @override
    def on_pre_start_async(cls, context: OnPreStartContext) -> None:
        package_name = cls.plugin_storage_path.name
        NodeManager.on_pre_start_async(
            context,
            cls.plugin_storage_path,
            ResourcePath('Packages', package_name, 'typescript-language-server'),
            Path('node_modules', 'typescript-language-server', 'lib', 'cli.mjs'),
            node_version_requirement='>=20',
        )
        plugins = context.configuration.initialization_options.get('plugins') or []
        for ts_plugin in cls._get_typescript_plugins():
            plugin: TypescriptPluginContribution = {
                'name': ts_plugin['name'],
                'location': ts_plugin['location'],
            }
            if 'languages' in ts_plugin:
                plugin['languages'] = ts_plugin['languages']
            plugins.append(plugin)
        context.configuration.initialization_options.set('plugins', plugins)

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
        if (
            (session := self.weaksession())
            and (status_text := session.config.settings.get('statusText'))
            and isinstance(status_text, str)
            and (status_text := status_text.replace('$version', params['version']).replace('$source', params['source']))
        ):
            session.set_config_status_async(status_text)

    def on_pre_send_response_async(self, response: ClientResponse) -> None:
        if response['method'] == 'workspace/configuration':
            if not (session := self.weaksession()):
                return
            for index, item in enumerate(response['params']['items']):
                if (
                    item.get('section') == 'formattingOptions'
                    and (scope_uri := item.get('scopeUri'))
                    and (buf := session.get_session_buffer_for_uri_async(scope_uri))
                    and (session_view := next(iter(buf.session_views), None))
                ):
                    view_settings = session_view.view.settings()
                    result = response['result'][index]
                    response['result'][index] = {
                        **(result if isinstance(result, dict) else {}),
                        'tabSize': view_settings.get('tab_size'),
                        'insertSpaces': view_settings.get('translate_tabs_to_spaces'),
                    }
            return

    @command_handler('_typescript.applyRefactoring')
    def on_apply_refactoring(self, arguments: list[ApplyRefactoringArgument] | None) -> Promise[None]:
        if not arguments or not (session := self.weaksession()):
            return Promise.resolve(None)
        argument = arguments[0]
        if argument['action'] == 'Move to file':
            if 'interactiveRefactorArguments' in argument:
                # Already augmented.
                return self._send_typescript_apply_refactoring_command(session, arguments)
            session.window.show_quick_panel([i['title'] for i in MOVE_TO_FILE_QUICK_PANEL_ITEMS],
                                            partial(self._on_move_file_action_select, arguments))
            return Promise.resolve(None)
        return self._send_typescript_apply_refactoring_command(session, arguments)

    def _on_move_file_action_select(self, arguments: list[ApplyRefactoringArgument], selected_index: int) -> None:
        if selected_index == -1:
            return
        session = self.weaksession()
        if not session:
            return
        item = MOVE_TO_FILE_QUICK_PANEL_ITEMS[selected_index]
        argument = arguments[0]
        if item['id'] == MoveToFileQuickPanelItemId.ExistingFile:
            sublime.open_dialog(partial(self._on_file_selector_dialog_done, arguments), directory=argument['file'])
        elif item['id'] == MoveToFileQuickPanelItemId.NewFile:
            session.window.show_input_panel('New filename',
                                            str(Path(argument['file']).parent) + os.sep,
                                            on_done=lambda filepath: self._on_filepath_selected(filepath, arguments),
                                            on_change=None,
                                            on_cancel=self._on_no_file_selected)

    def _on_file_selector_dialog_done(self, arguments: list[ApplyRefactoringArgument], filename: str | list[str] | None) -> None:
        if isinstance(filename, str) and filename:
            self._on_filepath_selected(filename, arguments)
        else:
            self._on_no_file_selected()

    def _on_filepath_selected(self, filename: str, arguments: list[ApplyRefactoringArgument]) -> None:
        if Path(filename).is_dir():
            sublime.status_message('Error: selected path is a directory')
            return
        self._execute_move_to_file_command(filename, arguments)

    def _on_no_file_selected(self) -> None:
        sublime.status_message('No file selected')

    def _execute_move_to_file_command(self, filename: str, arguments: list[ApplyRefactoringArgument]) -> None:
        session = self.weaksession()
        if not session:
            return
        arguments[0]['interactiveRefactorArguments'] = {
            'targetFile': filename
        }
        self._send_typescript_apply_refactoring_command(session, arguments)

    def _send_typescript_apply_refactoring_command(
        self, session: Session, arguments: list[ApplyRefactoringArgument]
    ) -> Promise[None]:
        command: ExecuteCommandParams = {
            'command': '_typescript.applyRefactoring',
            'arguments': cast('list[LSPAny]', arguments)
        }
        return session.send_request_task(Request.executeCommand(command)) \
            .then(self._handle_move_to_file_command_result)

    def _handle_move_to_file_command_result(self, result: Error | None) -> None:
        if isinstance(result, Error):
            sublime.status_message(str(result))


def plugin_loaded() -> None:
    LspTypescriptPlugin.register()


def plugin_unloaded() -> None:
    LspTypescriptPlugin.unregister()
    LspTypescriptPlugin.typescript_plugins = None
