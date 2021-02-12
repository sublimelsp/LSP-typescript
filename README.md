# LSP-typescript

TypeScript and JavaScript support for Sublime's LSP plugin provided through [Theia TypeScript Language Server](https://github.com/theia-ide/typescript-language-server).

### Installation

 * Install [`LSP`](https://packagecontrol.io/packages/LSP) and `LSP-typescript` from Package Control.
 * For ST3: If you use TypeScript install [TypeScript Syntax](https://packagecontrol.io/packages/TypeScript%20Syntax). If you use React install [JSCustom](https://packagecontrol.io/packages/JSCustom).
 * For ST4: The TypeScript and React (TSX) syntaxes are built-in so no need to install anything else.
 * Restart Sublime.

### Configuration

Open the configuration file using the Command Palette's `Preferences: LSP-typescript Settings` command or open it from the Sublime menu.

### Organize Imports command

To sort or remove unused imports you can trigger the `LSP-typescript: Organize Imports` command from the Command Palette or bind that command to a key binding. For example:

```json
    { "keys": ["ctrl+k"], "command": "lsp_execute",
        "args": {
            "session_name": "LSP-typescript",
            "command_name": "_typescript.organizeImports",
            "command_args": ["${file}"]
        }
    },
```
