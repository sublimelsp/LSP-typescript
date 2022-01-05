from LSP.plugin.core.file_watcher import FileWatcher
from LSP.plugin.core.file_watcher import FileWatcherEvent
from LSP.plugin.core.file_watcher import FileWatcherProtocol
from LSP.plugin.core.file_watcher import get_file_watcher_implementation
from LSP.plugin.core.typing import List
from typing import Optional
import os
import sublime


def register_rename_import_file_watcher(root_path: str) -> Optional[FileWatcher]:
    file_watcher = get_file_watcher_implementation()
    watcher = None
    if file_watcher:
        watcher = file_watcher.create(
            root_path=root_path,
            patterns=["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"],
            events=["create", "delete"],
            ignores=['**/node_modules/**'],
            handler=HandleRenameImport
        )
    return watcher


queued_events = []  # type: List[FileWatcherEvent]


class HandleRenameImport(FileWatcherProtocol):
    def on_file_event_async(events: List[FileWatcherEvent]) -> None:
        global queued_events
        queued_events.append(events[0])
        sublime.set_timeout(check_if_there_was_a_rename, 10)


def check_if_there_was_a_rename():
    global queued_events
    if len(queued_events) == 2:
        first_event, new_name = queued_events[0]
        second_event, old_name = queued_events[1]
        if (first_event == 'create' and second_event == 'delete'):
            # Rename detected
            prompt_rename(old_name, new_name)
    queued_events = []


def prompt_rename(old_name: str, new_name: str) -> None:
    settings = sublime.load_settings("LSP-typescript.sublime-settings")
    update_imports_on_file_move_setting = settings.get('settings', {}).get('updateImportsOnFileMove', "prompt")
    if update_imports_on_file_move_setting == "never":
        return
    w = sublime.active_window()
    if not w:
        return

    def apply_rename_on_server():
        w.run_command('lsp_execute', {
            "session_name": "LSP-typescript",
            "command_name": "_typescript.applyRenameFile",
            "command_args": [{
                "sourceUri": old_name,
                "targetUri": new_name
            }]
        })

    if update_imports_on_file_move_setting == 'prompt':
        items = [
            sublime.QuickPanelItem('Yes', 'Update imports.'),
            sublime.QuickPanelItem('No', 'Do not update imports.')
        ]
        old_base_file_name = os.path.basename(old_name)
        placeholder = "Update import paths for '{}'?".format(old_base_file_name)

        def on_select(index):
            if index == -1:
                return
            if items[index].trigger == 'Yes':
                apply_rename_on_server()

        w.show_quick_panel(items, on_select, placeholder=placeholder)

    if update_imports_on_file_move_setting == "always":
        apply_rename_on_server()
