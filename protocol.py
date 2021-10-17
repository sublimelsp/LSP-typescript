from LSP.plugin.core.protocol import Location, Position, RangeLsp, TextDocumentIdentifier
from LSP.plugin.core.typing import Any, List, Literal, Optional, TypedDict, Union


CallsDirection = Union[Literal['incoming'], Literal['outgoing']]

CallsRequestParams = TypedDict('CallsRequestParams', {
    'textDocument': TextDocumentIdentifier,
    'position': Position,
    'direction': CallsDirection
}, total=True)

DefinitionSymbol = TypedDict('DefinitionSymbol', {
    'name': str,
    'detail': Optional[str],
    'kind': int,
    'location': Location,
    'selectionRange': RangeLsp,
}, total=True)

Call = TypedDict('Call', {
    'location': Location,
    'symbol': DefinitionSymbol,
}, total=True)

CallsResponse = TypedDict('CallsResponse', {
    'symbol': Optional[DefinitionSymbol],
    'calls': List[Call],
}, total=True)

InlayHintKind = Union[Literal['Type'], Literal['Parameter'], Literal['Enum']]

InlayHint = TypedDict('InlayHint', {
    'text': str,
    'position': Position,
    'kind': InlayHintKind,
    'whitespaceBefore': bool,  # optional key
    'whitespaceAfter': bool,  # optional key
}, total=True)

InlayHintRequestParams = TypedDict('CallsRequestParams', {
    'textDocument': TextDocumentIdentifier,
    'range': RangeLsp  # optional key
}, total=False)

InlayHintResponse = TypedDict('CallsResponse', {
    'inlayHints': List[InlayHint]
}, total=True)

TypescriptLocation = TypedDict('TypescriptLocation', {
    'line': int,
    'offset': int,
}, total=True)

CodeEdit = TypedDict('CodeEdit', {
    'start': TypescriptLocation,
    'end': TypescriptLocation,
    'newText': str,
}, total=True)

FileCodeEdit = TypedDict('FileCodeEdits', {
    'fileName': str,
    'textChanges': List[CodeEdit],
}, total=True)

CompletionCodeActionCommand = TypedDict('CompletionCodeActionCommand', {
    'commands': List[Any],
    'description': str,
    'changes': List[FileCodeEdit],
}, total=True)
