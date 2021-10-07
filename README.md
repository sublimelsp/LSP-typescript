# LSP-typescript

TypeScript and JavaScript support for Sublime's LSP plugin provided through [Theia TypeScript Language Server](https://github.com/theia-ide/typescript-language-server).

## Installation

 * Install [`LSP`](https://packagecontrol.io/packages/LSP) and `LSP-typescript` from Package Control.
 * For ST3: If you use TypeScript install [TypeScript Syntax](https://packagecontrol.io/packages/TypeScript%20Syntax). If you use React install [JSCustom](https://packagecontrol.io/packages/JSCustom).
 * For ST4: The TypeScript and React (TSX) syntaxes are built-in so no need to install anything else.
 * Restart Sublime.

## Configuration

Open the configuration file using the Command Palette `Preferences: LSP-typescript Settings` command or open it from the Sublime menu.

## Organize Imports command

To sort or remove unused imports you can trigger the `LSP-typescript: Organize Imports` command from the Command Palette or create a key binding. For example:

```json
    { "keys": ["ctrl+k"], "command": "lsp_execute",
        "args": {
            "session_name": "LSP-typescript",
            "command_name": "_typescript.organizeImports",
            "command_args": ["${file}"]
        }
    },
```

## Find Callers command

The `LSP-typescript: Find Callers` command can be used to find what is calling the given symbol. It has some overlap with the built-in `LSP: Find References` command but returns only the places where the symbol was called.


## Inlay hints

Inlay hints are short textual annotations that show the parameter names, type hints.

![inlay-hints](/images/inlay-hints.png)

Inlay hints are disabled by default, but you can enable them by pasting the following block of code to LSP-typescript settings.

```json
// Settings in here override those in "LSP-typescript/LSP-typescript.sublime-settings"

{
  "initializationOptions": {
    "preferences": {
      "includeInlayEnumMemberValueHints": true,
      "includeInlayFunctionLikeReturnTypeHints": true,
      "includeInlayFunctionParameterTypeHints": true,
      "includeInlayParameterNameHints": "all",
      "includeInlayParameterNameHintsWhenArgumentMatchesName": true,
      "includeInlayPropertyDeclarationTypeHints": true,
      "includeInlayVariableTypeHints": true,
    }
  }
}

```

## Usage in projects that also use Flow

TypeScript can [check vanilla JavaScript](https://www.typescriptlang.org/docs/handbook/type-checking-javascript-files.html), but may break on JavaScript with Flow types in it. To keep LSP-typescript enabled for TS and vanilla JS, while ignoring Flow-typed files, you must install [JSCustom](https://packagecontrol.io/packages/JSCustom) and configure it like so:

```json
{
  "configurations": {
    "Flow": {
      "scope": "source.js.flow",
      "flow_types": true,
      "jsx": true
    }
  }
}
```

Also install [ApplySyntax](https://packagecontrol.io/packages/ApplySyntax) and configure it like so:

```json
{
  "syntaxes": [
    {
      "syntax": "User/JS Custom/Syntaxes/Flow",
      "match": "all",
      "rules": [
        { "file_path": ".*\\.jsx?$" },
        { "first_line": "^/[/\\*] *@flow" }
      ]
    }
  ]
}
```

And then configure LSP-typescript like so:

```json
{
  "selector": "source.js - source.js.flow, source.jsx, source.ts, source.tsx"
}
```

This works only on Sublime Text 4, and your project must have a `// @flow` or `/* @flow */` in each Flow-typed file. For more information, see [this issue](https://github.com/sublimelsp/LSP-typescript/issues/60).
