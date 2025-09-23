from __future__ import annotations
from LSP.plugin.core.protocol import Location, Position
from LSP.plugin.core.typing import List, Literal, NotRequired, StrEnum, Tuple, TypedDict, Union


class TypescriptVersionNotificationParams(TypedDict):
    version: str
    source: Union[Literal['bundled'], Literal['user-setting'], Literal['workspace']]

class TypescriptPluginContribution(TypedDict):
    name: str
    languages: List[str]
    location: str
    selector: str

class ApplyRefactoringInteractiveRefactorArguments(TypedDict):
    targetFile: str  # noqa: N815

class ApplyRefactoringArgument(TypedDict):
    file: str
    action: str
    interactiveRefactorArguments: NotRequired[ApplyRefactoringInteractiveRefactorArguments]  # noqa: N815

class ApplyRefactoringCommand(TypedDict):
    command: str
    arguments: Tuple[ApplyRefactoringArgument]

class MoveToFileQuickPanelItemId(StrEnum):
    ExistingFile = 'existing_file'
    NewFile = 'new_file'

class MoveToFileQuickPanelItem(TypedDict):
    id: MoveToFileQuickPanelItemId
    title: str

class ShowReferencesCommand(TypedDict):
    command: str
    arguments: Tuple[str, Position, List[Location]]
