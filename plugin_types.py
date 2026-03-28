from __future__ import annotations

from LSP.plugin.core.typing import StrEnum
from LSP.protocol import Location
from LSP.protocol import Position
from LSP.protocol import URI
from typing import List
from typing import Literal
from typing import Tuple
from typing import TypedDict
from typing_extensions import NotRequired


class TypescriptVersionNotificationParams(TypedDict):
    version: str
    source: Literal['bundled', 'user-setting', 'workspace']


class TypescriptPluginContribution(TypedDict):
    name: str
    languages: NotRequired[list[str]]
    location: str
    selector: NotRequired[str]


class ApplyRefactoringInteractiveRefactorArguments(TypedDict):
    targetFile: str


class ApplyRefactoringArgument(TypedDict):
    file: str
    action: str
    interactiveRefactorArguments: NotRequired[ApplyRefactoringInteractiveRefactorArguments]


class ApplyRefactoringCommand(TypedDict):
    command: str
    arguments: tuple[ApplyRefactoringArgument]


class MoveToFileQuickPanelItemId(StrEnum):
    ExistingFile = 'existing_file'
    NewFile = 'new_file'


class MoveToFileQuickPanelItem(TypedDict):
    id: MoveToFileQuickPanelItemId
    title: str


ShowReferencesArguments = Tuple[URI, Position, List[Location]]
