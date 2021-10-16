from .protocol import InlayHint, InlayHintRequestParams, InlayHintResponse, CompletionCodeActionCommand
from html import escape as html_escape
from LSP.plugin import ClientConfig
from LSP.plugin import SessionBufferProtocol
from LSP.plugin import uri_to_filename
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.typing import Any, Callable, Dict, List, Mapping, Optional
from LSP.plugin.core.views import point_to_offset
from LSP.plugin.core.views import text_document_identifier
from lsp_utils import ApiWrapperInterface
from lsp_utils import NpmClientHandler
from lsp_utils import request_handler
import os
import sublime

try:
    from LSP.plugin.core.edit import apply_workspace_edit
    from LSP.plugin.core.edit import TextEditTuple
except ImportError:
    # Not supported in ST3
    TextEditTuple = Any
    pass


def plugin_loaded() -> None:
    LspTypescriptPlugin.setup()


def plugin_unloaded() -> None:
    LspTypescriptPlugin.cleanup()


def inlay_hint_to_phantom(view: sublime.View, hint: InlayHint) -> sublime.Phantom:
    html = """
    <body id="lsp-typescript">
        <style>
            .inlay-hint {{
                color: color(var(--foreground) alpha(0.6));
                background-color: color(var(--foreground) alpha(0.08));
                border-radius: 4px;
                padding: 0.05em 4px;
                font-size: 0.9em;
            }}
        </style>
        <div class="inlay-hint">
            {label}
        </div>
    </body>
    """
    point = Point.from_lsp(hint['position'])
    region = sublime.Region(point_to_offset(point, view))
    label = html_escape(hint["text"])
    html = html.format(label=label)
    return sublime.Phantom(region, html, sublime.LAYOUT_INLINE)


def to_lsp_edits(items: List[CompletionCodeActionCommand]) -> Dict[str, List[TextEditTuple]]:
    workspace_edits = {}  # type: Dict[str, List[TextEditTuple]]
    for item in items:
        for change in item['changes']:
            file_changes = []  # List[TextEditTuple]
            for text_change in change['textChanges']:
                start = text_change['start']
                end = text_change['end']
                file_changes.append(
                    (
                        (start['line'] - 1, start['offset'] - 1),
                        (end['line'] - 1, end['offset'] - 1),
                        text_change['newText'].replace("\r", ""),
                        None,
                    )
                )
            workspace_edits[change['fileName']] = file_changes
    return workspace_edits


class LspTypescriptPlugin(NpmClientHandler):
    package_name = __package__
    server_directory = 'typescript-language-server'
    server_binary_path = os.path.join(server_directory, 'node_modules', 'typescript-language-server', 'lib', 'cli.js')

    @classmethod
    def is_allowed_to_start(
        cls,
        window: sublime.Window,
        initiating_view: Optional[sublime.View] = None,
        workspace_folders: Optional[List[WorkspaceFolder]] = None,
        configuration: Optional[ClientConfig] = None
    ) -> Optional[str]:
        if not workspace_folders:
            return 'This server only works when the window workspace includes some folders!'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._api = None  # type: Optional[ApiWrapperInterface]
        super().__init__(*args, **kwargs)

    def on_ready(self, api: ApiWrapperInterface) -> None:
        self._api = api

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

    # --- AbstractPlugin handlers --------------------------------------------------------------------------------------

    def on_session_buffer_changed_async(self, session_buffer: SessionBufferProtocol) -> None:
        self._request_inlay_hints_async(session_buffer)

    def on_pre_server_command(self, command: Mapping[str, Any], done_callback: Callable[[], None]) -> bool:
        if command['command'] == '_typescript.applyCompletionCodeAction':
            _, items = command['arguments']
            session = self.weaksession()
            if session:
                apply_workspace_edit(session.window, to_lsp_edits(items)).then(lambda _: done_callback())
                return True
        return False

    # --- Inlay Hints handlers -----------------------------------------------------------------------------------------

    def _request_inlay_hints_async(self, session_buffer: SessionBufferProtocol) -> None:
        if not self._api:
            return
        uri = session_buffer.get_uri()
        if not uri:
            return
        params = {"textDocument": text_document_identifier(uri)}  # type: InlayHintRequestParams
        self._api.send_request(
            "typescript/inlayHints", params,
            lambda result, success: self._on_inlay_hints_async(result, success, session_buffer))

    def _on_inlay_hints_async(
        self, response: InlayHintResponse, is_error: bool, session_buffer: SessionBufferProtocol
    ) -> None:
        if is_error:
            return
        view = next(iter(session_buffer.session_views)).view
        if not view:
            return
        key = "_lsp_typescript_inlay_hints"
        phantom_set = getattr(session_buffer, key, None)
        if phantom_set is None:
            phantom_set = sublime.PhantomSet(view, key)
            setattr(session_buffer, key, phantom_set)
        phantoms = [inlay_hint_to_phantom(view, hint) for hint in response['inlayHints']]
        sublime.set_timeout(lambda: self.present_inlay_hints(view, phantoms, phantom_set))

    def present_inlay_hints(
        self, view: sublime.View, phantoms: List[sublime.Phantom], phantom_set: sublime.PhantomSet
    ) -> None:
        if not view.is_valid():
            return
        phantom_set.update(phantoms)
