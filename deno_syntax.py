import os
import re
import sublime
import sublime_plugin


RE_DENO_DEPS_CACHES_DIRPATH = re.compile(r".+\/deno\/deps\/.+", re.IGNORECASE)


class DenoSyntaxListener(sublime_plugin.EventListener):
    def on_load_async(self, view: sublime.View):
        self.check_deno_syntax(view)

    def check_deno_syntax(self, view: sublime.View):
        if not (file_name := view.file_name()):
            return
        if not (view.scope_name(0).startswith("text.plain")):
            return
        if not RE_DENO_DEPS_CACHES_DIRPATH.match(file_name):
            return
        self.set_deno_syntax(view, "d." + os.path.basename(file_name[0:-60]) + ".ts")

    def set_deno_syntax(self, view: sublime.View, name: str):
        view.set_read_only(True)
        view.set_name(name)
        view.assign_syntax(sublime.find_syntax_for_file(name))
