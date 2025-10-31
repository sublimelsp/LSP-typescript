from __future__ import annotations
from LSP.plugin.core.typing import StrEnum
from typing import TYPE_CHECKING, Literal, TypedDict
from typing_extensions import NotRequired

if TYPE_CHECKING:
    from LSP.protocol import Location, Position


class TypescriptVersionNotificationParams(TypedDict):
    version: str
    source: Literal['bundled', 'user-setting', 'workspace']


class TypescriptPluginContribution(TypedDict):
    name: str
    languages: NotRequired[list[str]]
    location: str
    selector: NotRequired[str]


class ApplyRefactoringInteractiveRefactorArguments(TypedDict):
    targetFile: str  # noqa: N815


class ApplyRefactoringArgument(TypedDict):
    file: str
    action: str
    interactiveRefactorArguments: NotRequired[ApplyRefactoringInteractiveRefactorArguments]  # noqa: N815


class ApplyRefactoringCommand(TypedDict):
    command: str
    arguments: tuple[ApplyRefactoringArgument]


class MoveToFileQuickPanelItemId(StrEnum):
    ExistingFile = 'existing_file'
    NewFile = 'new_file'


class MoveToFileQuickPanelItem(TypedDict):
    id: MoveToFileQuickPanelItemId
    title: str


class ShowReferencesCommand(TypedDict):
    command: str
    arguments: tuple[str, Position, list[Location]]
