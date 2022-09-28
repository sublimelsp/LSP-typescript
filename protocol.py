from LSP.plugin.core.protocol import Location, Position, Range, TextDocumentIdentifier
from LSP.plugin.core.typing import List, Literal, Optional, TypedDict, Union


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
    'selectionRange': Range,
}, total=True)

Call = TypedDict('Call', {
    'location': Location,
    'symbol': DefinitionSymbol,
}, total=True)

CallsResponse = TypedDict('CallsResponse', {
    'symbol': Optional[DefinitionSymbol],
    'calls': List[Call],
}, total=True)
