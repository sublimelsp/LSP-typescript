from .protocol import InlayHint, InlayHintRequestParams, InlayHintResponse
from html import escape as html_escape
from LSP.plugin import Request
from LSP.plugin import Session
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.registry import windows
from LSP.plugin.core.types import debounced
from LSP.plugin.core.types import FEATURES_TIMEOUT
from LSP.plugin.core.typing import List, Optional, Tuple
from LSP.plugin.core.views import point_to_offset
from LSP.plugin.core.views import region_to_range
from LSP.plugin.core.views import text_document_identifier
import sublime
import sublime_plugin


def inlay_hint_to_phantom(view: sublime.View, hint: InlayHint) -> sublime.Phantom:
    html = """
    <body id="lsp-typescript-inlay-hints">
        <style>
            body {{
                padding: 0;
                margin: 0px;
                border: 0px;
                font-size: 0.9em;
            }}

            .lsp-typescript-inlay-hints {{
                color: color(var(--foreground) alpha(0.6));
                background-color: color(var(--foreground) alpha(0.08));
                border-radius: 4px;
                padding: 2px;
            }}
        </style>
        <div class="lsp-typescript-inlay-hints">
            {label}
        </div>
    </body>
    """
    point = Point.from_lsp(hint['position'])
    region = sublime.Region(point_to_offset(point, view))
    label = html_escape(hint["text"])
    html = html.format(label=label)
    return sublime.Phantom(region, html, sublime.LAYOUT_INLINE)


def session_by_name(view: sublime.View, session_name: str, capability_path: Optional[str] = None) -> Optional[Session]:
    listener = windows.listener_for_view(view)
    if listener:
        for sv in listener.session_views_async():
            if sv.session.config.name == session_name:
                if capability_path is None or sv.has_capability_async(capability_path):
                    return sv.session
                else:
                    return None
    return None


class InlayHintsListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._stored_region = sublime.Region(-1, -1)
        self.phantom_set = sublime.PhantomSet(view, "_lsp_typescript_inlay_hints")

    def _update_stored_region_async(self) -> Tuple[bool, sublime.Region]:
        sel = self.view.sel()
        if not sel:
            return False, sublime.Region(-1, -1)
        region = sel[0]
        if self._stored_region != region:
            self._stored_region = region
            return True, region
        return False, sublime.Region(-1, -1)

    def on_modified_async(self) -> None:
        different, region = self._update_stored_region_async()
        if not different:
            return
        debounced(
            self.request_inlay_hints_async,
            FEATURES_TIMEOUT,
            lambda: self._stored_region == region,
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
        phantoms = [inlay_hint_to_phantom(self.view, hint) for hint in response['inlayHints']]
        sublime.set_timeout(lambda: self.present_inlay_hints(phantoms))

    def present_inlay_hints(self, phantoms: List[sublime.Phantom]) -> None:
        if not self.view.is_valid():
            return
        self.phantom_set.update(phantoms)

