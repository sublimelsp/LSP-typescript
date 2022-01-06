from LSP.plugin.core.file_watcher import FileWatcher
from LSP.plugin.core.file_watcher import FileWatcherEvent
from LSP.plugin.core.file_watcher import FileWatcherProtocol
from LSP.plugin.core.typing import List, Type
import os
import sublime


class HandleRenameImport(FileWatcherProtocol):
    def __init__(self, window: sublime.Window, root_path: str, file_watcher: Type[FileWatcher]):
        self.window = window
        self.events = []  # type: List[FileWatcherEvent]
        self.file_watcher = file_watcher.create(
            root_path=root_path,
            patterns=["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"],
            events=["create", "delete"],
            ignores=['**/node_modules/**'],
            handler=self
        )

    def clean_up(self):
        self.file_watcher.destroy()

    def on_file_event_async(self, events: List[FileWatcherEvent]) -> None:
        self.events.extend(events)
        sublime.set_timeout_async(self._check_if_there_was_a_rename, 10)

    def _check_if_there_was_a_rename(self):
        if len(self.events) == 2:
            create_event = next((event for event in self.events if event[0] == 'create'), None)
            delete_event = next((event for event in self.events if event[0] == 'delete'), None)
            if create_event and delete_event:
                # Rename detected
                new_name = create_event[1]
                old_name = delete_event[1]
                self.prompt_rename(old_name, new_name)
        self.events = []

    def prompt_rename(self, old_name: str, new_name: str) -> None:
        settings = sublime.load_settings("LSP-typescript.sublime-settings")
        update_imports_on_file_move_setting = settings.get('settings', {}).get('updateImportsOnFileMove', "prompt")
        if update_imports_on_file_move_setting == "always":
            self.apply_rename_on_server(old_name, new_name)
            return
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
                    self.apply_rename_on_server(old_name, new_name)

            self.window.show_quick_panel(items, on_select, placeholder=placeholder)

    def apply_rename_on_server(self, old_name: str, new_name: str):
        self.window.run_command('lsp_execute', {
            "session_name": "LSP-typescript",
            "command_name": "_typescript.applyRenameFile",
            "command_args": [{
                "sourceUri": old_name,
                "targetUri": new_name
            }]
        })
