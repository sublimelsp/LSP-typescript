import os
from lsp_utils import NpmClientHandler


def plugin_loaded():
    LspTypescriptPlugin.setup()


def plugin_unloaded():
    LspTypescriptPlugin.cleanup()


class LspTypescriptPlugin(NpmClientHandler):
    package_name = __package__
    server_directory = 'typescript-language-server'
    server_binary_path = os.path.join(
        server_directory, 'node_modules', 'typescript-language-server', 'lib', 'cli.js'
    )
