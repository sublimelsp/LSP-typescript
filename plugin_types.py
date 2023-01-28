from LSP.plugin.core.typing import Literal, TypedDict, Union


TypescriptVersionNotificationParams = TypedDict('TypescriptVersionNotificationParams', {
    'version': str,
    'source': Union[Literal['bundled'], Literal['user-setting'], Literal['workspace']]
})
