from __future__ import annotations
from LSP.plugin.core.typing import List, Literal, TypedDict, Union


TypescriptVersionNotificationParams = TypedDict('TypescriptVersionNotificationParams', {
    'version': str,
    'source': Union[Literal['bundled'], Literal['user-setting'], Literal['workspace']]
})

TypescriptPluginContribution = TypedDict('TypescriptPluginContribution', {
    'name': str,
    'languages': List[str],
    'location': str,
    'selector': str,
})
