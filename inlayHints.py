from .protocol import InlayHint, InlayHintRequestParams, InlayHintResponse
from html import escape as html_escape
from LSP.plugin import Request
from LSP.plugin import Session
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.registry import windows
from LSP.plugin.core.types import debounced
from LSP.plugin.core.types import FEATURES_TIMEOUT
from LSP.plugin.core.typing import List, Optional
from LSP.plugin.core.views import point_to_offset, uri_from_view
from LSP.plugin.core.views import text_document_identifier
import sublime
import sublime_plugin


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


def session_by_name(view: sublime.View, session_name: str) -> Optional[Session]:
    listener = windows.listener_for_view(view)
    if listener:
        for sv in listener.session_views_async():
            if sv.session.config.name == session_name:
                return sv.session
    return None


class InlayHintsListener(sublime_plugin.ViewEventListener):
    def on_modified_async(self) -> None:
        change_count = self.view.change_count()
        # increase the timeout to avoid rare issue with hints being requested before the textdocument/didChange
        TIMEOUT = FEATURES_TIMEOUT + 100
        debounced(
            self.request_inlay_hints_async,
            TIMEOUT,
            lambda: self.view.change_count() == change_count,
            async_thread=True,
        )

    def on_load_async(self) -> None:
        self.request_inlay_hints_async()

    def on_activated_async(self) -> None:
        self.request_inlay_hints_async()

    def request_inlay_hints_async(self) -> None:
        session = session_by_name(self.view, 'LSP-typescript')
        if session is None:
            return
        params = {
            "textDocument": text_document_identifier(self.view)
        }  # type: InlayHintRequestParams
        session.send_request_async(
            Request("typescript/inlayHints", params),
            self.on_inlay_hints_async
        )

    def on_inlay_hints_async(self, response: InlayHintResponse) -> None:
        session = session_by_name(self.view, 'LSP-typescript')
        if session is None:
            return
        buffer = session.get_session_buffer_for_uri_async(uri_from_view(self.view))
        if not buffer:
            return
        key = "_lsp_typescript_inlay_hints"
        phantom_set = getattr(buffer, key, None)
        if phantom_set is None:
            phantom_set = sublime.PhantomSet(self.view, key)
            setattr(buffer, key, phantom_set)
        phantoms = [inlay_hint_to_phantom(self.view, hint) for hint in response['inlayHints']]
        sublime.set_timeout(lambda: self.present_inlay_hints(phantoms, phantom_set))

    def present_inlay_hints(self, phantoms: List[sublime.Phantom], phantom_set: sublime.PhantomSet) -> None:
        if not self.view.is_valid():
            return
        phantom_set.update(phantoms)
