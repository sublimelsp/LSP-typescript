from __future__ import annotations

from .plugin_types import ApplyRefactoringArgument
from .plugin_types import MoveToFileQuickPanelItem
from .plugin_types import MoveToFileQuickPanelItemId
from .plugin_types import TypescriptPluginContribution
from .plugin_types import TypescriptVersionNotificationParams
from functools import partial
from LSP.plugin import ClientRequest
from LSP.plugin import ClientResponse
from LSP.plugin import command_handler
from LSP.plugin import Error
from LSP.plugin import IsApplicableContext
from LSP.plugin import LspPlugin
from LSP.plugin import notification_handler
from LSP.plugin import OnPreStartContext
from LSP.plugin import parse_uri
from LSP.plugin import position_to_offset
from LSP.plugin import Promise
from LSP.plugin import Request
from LSP.plugin import request_handler
from LSP.plugin import ServerResponse
from LSP.plugin import Session
from LSP.plugin import uri_from_view
from LSP.plugin import uri_handler
from LSP.protocol import DocumentUri
from LSP.protocol import ExecuteCommandParams
from LSP.protocol import Hover
from LSP.protocol import HoverParams
from LSP.protocol import LSPAny
from lsp_utils import NodeManager
from pathlib import Path
from sublime_lib import ResourcePath
from typing import Any
from typing import cast
from typing import ClassVar
from typing import final
from typing import TYPE_CHECKING
from typing_extensions import NotRequired
from typing_extensions import override
import os
import sublime
import sublime_plugin
import weakref

if TYPE_CHECKING:
    from LSP.protocol import TextDocumentPositionParams


MOVE_TO_FILE_QUICK_PANEL_ITEMS: list[MoveToFileQuickPanelItem] = [
    {'id': MoveToFileQuickPanelItemId.ExistingFile, 'title':  'Select existing file...'},
    {'id': MoveToFileQuickPanelItemId.NewFile, 'title': 'Enter new file path...'},
]


def log(message: str) -> None:
    print(f'[{__package__}] {message}')


def typescript_plugin_path(plugin: TypescriptPluginContribution) -> Path:
    return Path(plugin['location']) / plugin['name']


def to_server_plugin(plugin: TypescriptPluginContribution) -> TypescriptPluginContribution:
    """Return the plugin as passed to the server in the `plugins` initialization option."""
    server_plugin: TypescriptPluginContribution = {
        'name': plugin['name'],
        'location': plugin['location'],
    }
    if 'languages' in plugin:
        server_plugin['languages'] = plugin['languages']
    return server_plugin


@final
class LspTypescriptPlugin(LspPlugin):
    registered_plugins: ClassVar[dict[int, dict[str, TypescriptPluginContribution]]] = {}
    """Plugins registered with the `lsp_typescript_register_plugin` command, by window ID and plugin name."""
    instances: ClassVar[weakref.WeakSet[LspTypescriptPlugin]] = weakref.WeakSet()

    @classmethod
    @override
    def is_applicable_async(cls, context: IsApplicableContext) -> bool:
        if super().is_applicable_async(context):
            return True
        scheme, _ = parse_uri(uri_from_view(context.view))
        if scheme in context.configuration.schemes and (syntax := context.view.syntax()):
            for plugin in cls._get_window_plugins(context.view.window()):
                if (
                    (selector := plugin.get('selector'))
                    and sublime.score_selector(syntax.scope, selector) > 0
                    and typescript_plugin_path(plugin).exists()
                ):
                    return True
        return False

    @classmethod
    def register_plugin_async(cls, window: sublime.Window, plugin: TypescriptPluginContribution) -> None:
        """
        Load the plugin in the window's servers. Running servers that didn't load it are restarted.

        Called by packages whose plugin is only known once their server starts, for example because it has to match the
        version of that server, which the user can point to a custom location.
        """
        window_plugins = cls.registered_plugins.setdefault(window.id(), {})
        if window_plugins.get(plugin['name']) == plugin:
            return
        window_plugins[plugin['name']] = plugin
        server_plugin = to_server_plugin(plugin)
        for instance in list(cls.instances):
            if (
                (session := instance.weaksession())
                and session.window == window
                and not session.exiting
                and server_plugin not in (session.config.initialization_options.get('plugins') or [])
                and (session_view := next(iter(list(session.session_views_async())), None))
            ):
                # Restarting checks again which views the server applies to, including those of the plugin. The command
                # is only enabled in a view that has a session.
                session_view.view.run_command('lsp_restart_server', {'config_name': cls.name})
                return
        # Not running yet, or running without views. Start it for views that the plugin applies to.
        for view in window.views():
            view.run_command('lsp_check_applicable', {'session_name': cls.name})

    @classmethod
    @override
    def on_pre_start_async(cls, context: OnPreStartContext) -> None:
        package_name = cls.plugin_storage_path.name
        NodeManager.on_pre_start_async(
            context,
            cls.plugin_storage_path,
            ResourcePath('Packages', package_name, 'language-server'),
            Path('node_modules', 'typescript-language-server', 'lib', 'cli.mjs'),
            node_version_requirement='>=20',
        )
        plugins = context.configuration.initialization_options.get('plugins') or []
        for ts_plugin in cls._get_window_plugins(context.view.window()):
            if not (path := typescript_plugin_path(ts_plugin)).exists():
                log(f'Ignoring non-existent plugin at "{path}"')
                continue
            plugins.append(to_server_plugin(ts_plugin))
        context.configuration.initialization_options.set('plugins', plugins)

    @override
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._verbosity_hover_handler = VerbosityHoverHandler()
        LspTypescriptPlugin.instances.add(self)

    @classmethod
    def _get_window_plugins(cls, window: sublime.Window | None) -> list[TypescriptPluginContribution]:
        """Return the plugins registered for the window."""
        return list(cls.registered_plugins.get(window.id(), {}).values()) if window else []

    @request_handler('_typescript.rename')
    def on_typescript_rename(self, params: TextDocumentPositionParams) -> Promise[None]:
        _, filename = parse_uri(params['textDocument']['uri'])
        view = sublime.active_window().open_file(filename)
        if view:
            point = position_to_offset(view, params['position'])
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

    def on_pre_send_request_async(self, request: ClientRequest, view: sublime.View | None) -> None:
        if request['method'] == 'textDocument/hover':
            self._verbosity_hover_handler.on_hover_request(cast('HoverParamsWithVerbosity', request['params']))
            return

    def on_server_response_async(self, response: ServerResponse) -> None:
        if response['method'] == 'textDocument/hover':
            self._verbosity_hover_handler.on_hover_response(cast('VerbosityHover | None', response['result']))
            return

    @uri_handler('verbosity')
    def handle_verbosity_uri(self, uri: DocumentUri, _: sublime.NewFileFlags) -> Promise[sublime.Sheet | None]:
        if session := self.weaksession():
            verbosity_delta = int(uri.split(':')[1])
            self._verbosity_hover_handler.handle_verbosity_change(session, verbosity_delta)
        return Promise.resolve(None)

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
    LspTypescriptPlugin.registered_plugins.clear()


class LspTypescriptRegisterPluginCommand(sublime_plugin.WindowCommand):
    """
    Register a TypeScript plugin to load in this window.

    For packages that know where their plugin is only once their server starts. Run it from `on_pre_start_async`:

    .. code:: py

        window.run_command('lsp_typescript_register_plugin', {
            'name': '@vue/typescript-plugin',
            'location': '/path/to/node_modules',
            'languages': ['vue'],
            'selector': 'text.html.vue',
        })

    Registering it again with the same arguments does nothing. Registering a different `location` for the same `name`
    replaces it and restarts the servers that loaded the previous one.
    """

    def is_visible(self) -> bool:
        return False

    def run(self, name: str, location: str, languages: list[str] | None = None, selector: str | None = None) -> None:
        plugin: TypescriptPluginContribution = {'name': name, 'location': location}
        if languages:
            plugin['languages'] = languages
        if selector:
            plugin['selector'] = selector
        window = self.window
        sublime.set_timeout_async(lambda: LspTypescriptPlugin.register_plugin_async(window, plugin))


class HoverParamsWithVerbosity(HoverParams):
    verbosityLevel: NotRequired[int]


class VerbosityHover(Hover):
    canIncreaseVerbosityLevel: NotRequired[bool]


class VerbosityHoverHandler:

    def __init__(self) -> None:
        self._last_hover_params: HoverParamsWithVerbosity | None = None

    def on_hover_request(self, hover_params: HoverParamsWithVerbosity) -> None:
        if (
            self._last_hover_params
            and self._last_hover_params['position'] == hover_params['position']
            and self._last_hover_params['textDocument']['uri'] == hover_params['textDocument']['uri']
        ):
            verbosity_level = self._last_hover_params.get('verbosityLevel', 0)
        else:
            verbosity_level = 0
        self._last_hover_params = hover_params
        hover_params['verbosityLevel'] = verbosity_level

    def on_hover_response(self, hover_response: VerbosityHover | None) -> None:
        if not hover_response:
            self._last_hover_params = None
            return
        if (
            self._last_hover_params
            and (contents := hover_response['contents']) and isinstance(contents, dict) and 'kind' in contents
        ):
            verbosity_level = self._last_hover_params.get('verbosityLevel', 0)
            can_increase_verbosity = hover_response.get('canIncreaseVerbosityLevel')
            if verbosity_level > 0 or can_increase_verbosity:
                controls: list[str] = [
                    f'<kbd>{"[-](verbosity:-1)" if verbosity_level > 0 else "-"}</kbd>',
                    f'<kbd>{"[+](verbosity:+1)" if can_increase_verbosity else "+"}</kbd>',
                ]
                contents['value'] = f'{" ".join(controls)}\n{contents["value"]}'

    def handle_verbosity_change(self, session: Session, verbosity_delta: int) -> None:
        if not self._last_hover_params:
            return
        hover_params = self._last_hover_params
        verbosity_level = max(0, hover_params.get('verbosityLevel', 0) + verbosity_delta)
        hover_params['verbosityLevel'] = verbosity_level
        if session_buffer := session.get_session_buffer_for_uri_async(hover_params['textDocument']['uri']):
            view = session_buffer.get_view_in_group()
            point = position_to_offset(view, hover_params['position'])
            view.run_command('lsp_hover', {'point': point})
