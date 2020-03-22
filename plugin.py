import shutil
import os
import sublime

from LSP.plugin.core.handlers import LanguageHandler
from LSP.plugin.core.settings import ClientConfig, read_client_config
from LSP.plugin.core.rpc import Client
from LSP.plugin.core.views import point_to_offset
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.typing import Dict
from LSP.plugin.core.url import uri_to_filename
from lsp_utils import ServerNpmResource


PACKAGE_NAME = 'LSP-typescript'
SETTINGS_FILENAME = 'LSP-typescript.sublime-settings'
SERVER_DIRECTORY = 'typescript-language-server'
SERVER_BINARY_PATH = os.path.join(SERVER_DIRECTORY, 'node_modules', 'typescript-language-server', 'lib', 'cli.js')

server = ServerNpmResource(PACKAGE_NAME, SERVER_DIRECTORY, SERVER_BINARY_PATH)


def plugin_loaded():
    server.setup()


def plugin_unloaded():
    server.cleanup()


def is_node_installed():
    return shutil.which('node') is not None


class LspTypeScriptPlugin(LanguageHandler):
    @property
    def name(self) -> str:
        return PACKAGE_NAME.lower()

    @property
    def config(self) -> ClientConfig:
        # Calling setup() also here as this might run before `plugin_loaded`.
        # Will be a no-op if already ran.
        # See https://github.com/sublimelsp/LSP/issues/899
        server.setup()

        configuration = self.migrate_and_read_configuration()

        default_configuration = {
            'enabled': True,
            'command': ['node', server.binary_path, '--stdio'],
        }

        default_configuration.update(configuration)
        return read_client_config(self.name, default_configuration)

    def migrate_and_read_configuration(self) -> Dict:
        settings = {}
        loaded_settings = sublime.load_settings(SETTINGS_FILENAME)  # type: Dict

        if loaded_settings:
            if loaded_settings.has('client'):
                client = loaded_settings.get('client')  # type: Dict
                loaded_settings.erase('client')
                # Migrate old keys
                for key, value in client.items():
                    loaded_settings.set(key, value)
                sublime.save_settings(SETTINGS_FILENAME)

            # Read configuration keys
            for key in ['languages', 'initializationOptions', 'settings']:
                settings[key] = loaded_settings.get(key)

        return settings

    def on_start(self, window) -> bool:
        if not is_node_installed():
            sublime.status_message('Please install Node.js for the TypeScript Language Server to work.')
            return False
        return True

    def on_initialized(self, client: Client) -> None:
        client.on_request(
            "_typescript.rename", lambda params, token: self._on_typescript_rename(params, token))

    def _on_typescript_rename(self, textDocumentPositionParams, cancellationToken):
        view = sublime.active_window().open_file(
            uri_to_filename(textDocumentPositionParams['textDocument']['uri'])
        )

        if not view:
            return

        lsp_point = Point.from_lsp(textDocumentPositionParams['position'])
        point = point_to_offset(lsp_point, view)

        sel = view.sel()
        sel.clear()
        sel.add_all([point])
        view.run_command('lsp_symbol_rename')
