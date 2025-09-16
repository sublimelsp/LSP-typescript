from __future__ import annotations
from .plugin_types import ApplyRefactoringCommand, ShowReferencesCommand, TypescriptVersionNotificationParams
from functools import partial
from LSP.plugin import uri_to_filename
from LSP.plugin.core.protocol import Point, TextDocumentPositionParams, ExecuteCommandParams
from LSP.plugin.core.typing import Callable, Tuple, cast
from LSP.plugin.core.views import point_to_offset
from LSP.plugin.locationpicker import LocationPicker
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
            if 'interactiveRefactorArguments' in argument:
                # Already augmented.
                return False
            sublime.open_dialog(partial(self._on_file_selected, command), directory=argument['file'])
            return True
        return False

    def _on_file_selected(self, command: ApplyRefactoringCommand, filename: str | list[str] | None) -> None:
        if not filename or isinstance(filename, list):
            sublime.status_message('No file selected')
            return
        command['arguments'][0]['interactiveRefactorArguments'] = {
            'targetFile': filename
        }
        session = self.weaksession()
        if not session:
            return
        session.execute_command(cast('ExecuteCommandParams', command), progress=False)
