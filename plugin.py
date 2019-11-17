import shutil
import os
import sublime
import threading
import subprocess

from LSP.plugin.core.handlers import LanguageHandler
from LSP.plugin.core.settings import ClientConfig, read_client_config
from LSP.plugin.core.rpc import Client
from LSP.plugin.core.views import point_to_offset
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.url import uri_to_filename


package_path = os.path.dirname(__file__)
server_path = os.path.join(
    package_path,
    'node_modules',
    'typescript-language-server',
    'lib',
    'cli.js'
)

def plugin_loaded():
    is_server_installed = os.path.isfile(server_path)
    print('LSP-typescript: Server {} installed.'.format('is' if is_server_installed else 'is not' ))

    # install the node_modules if not installed
    if not is_server_installed:
        # this will be called only when the plugin gets:
        # - installed for the first time,
        # - or when updated on package control
        logAndShowMessage('LSP-typescript: Installing server.')

        runCommand(
            onCommandDone,
            ["npm", "install", "--verbose", "--prefix", package_path, package_path]
        )


def onCommandDone():
    logAndShowMessage('LSP-typescript: Server installed.')


def runCommand(onExit, popenArgs):
    """
    Runs the given args in a subprocess.Popen, and then calls the function
    onExit when the subprocess completes.
    onExit is a callable object, and popenArgs is a list/tuple of args that
    would give to subprocess.Popen.
    """
    def runInThread(onExit, popenArgs):
        try:
            if sublime.platform() == 'windows':
                subprocess.check_call(popenArgs, shell=True)
            else:
                subprocess.check_call(popenArgs)
            onExit()
        except subprocess.CalledProcessError as error:
            logAndShowMessage('LSP-typescript: Error while installing the server.', error)
        return
    thread = threading.Thread(target=runInThread, args=(onExit, popenArgs))
    thread.start()
    # returns immediately after the thread starts
    return thread


def is_node_installed():
    return shutil.which('node') is not None


def logAndShowMessage(msg, additional_logs=None):
    print(msg, '\n', additional_logs) if additional_logs else print(msg)
    sublime.active_window().status_message(msg)


def on_typescript_rename(textDocumentPositionParams, cancellationToken):
    view = sublime.active_window().open_file(
        uri_to_filename(
            textDocumentPositionParams['textDocument']['uri']
        )
    )

    if not view:
        return

    lsp_point = Point.from_lsp(textDocumentPositionParams['position'])
    point = point_to_offset(lsp_point, view)

    sel = view.sel()
    sel.clear()
    sel.add_all([point])
    view.run_command('lsp_symbol_rename')


class SharedState:
    def on_start(self, window) -> bool:
        if not is_node_installed():
            sublime.status_message('Please install Node.js for the TypeScript Language Server to work.')
            return False
        return True

    def on_initialized(self, client: Client) -> None:
        client.on_request(
            "_typescript.rename",
            lambda params, token: on_typescript_rename(params, token))


class LspTypeScriptPlugin(SharedState, LanguageHandler):
    @property
    def name(self) -> str:
        return 'lsp-typescript'

    @property
    def config(self) -> ClientConfig:
        settings = sublime.load_settings("LSP-typescript.sublime-settings")
        client_configuration = settings.get('client')

        default_configuration = {
            "command": [
                "node",
                server_path,
                '--stdio'
            ],
            "languages": [
                {
                    "languageId": "typescript",
                    "scopes": [
                        "source.ts",
                        "source.tsx"
                    ],
                    "syntaxes": [
                        "Packages/TypeScript Syntax/TypeScript.tmLanguage",
                        "Packages/TypeScript Syntax/TypeScriptReact.tmLanguage"
                    ]
                }
            ],
            "initializationOptions": {}
        }

        default_configuration.update(client_configuration)
        return read_client_config('lsp-typescript', default_configuration)


class LspJavaScriptPlugin(SharedState, LanguageHandler):
    @property
    def name(self) -> str:
        return 'lsp-javascript'

    @property
    def config(self) -> ClientConfig:
        settings = sublime.load_settings("LSP-javascript.sublime-settings")
        client_configuration = settings.get('client')

        default_configuration = {
            "command": [
                "node",
                server_path,
                '--stdio'
            ],
            "languages": [
                {
                    "languageId": "javascript",
                    "scopes": [
                        "source.js",
                        "source.jsx"
                    ],
                    "syntaxes": [
                        "Packages/User/JS Custom/Syntaxes/React.sublime-syntax",
                        "Packages/JavaScript/JavaScript.sublime-syntax",
                        "Packages/Babel/JavaScript (Babel).sublime-syntax"
                    ]
                }
            ],
            "initializationOptions": {}
        }

        default_configuration.update(client_configuration)
        return read_client_config('lsp-javascript', default_configuration)

