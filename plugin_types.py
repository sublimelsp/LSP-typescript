from __future__ import annotations
from LSP.plugin.core.protocol import Location, Position
from LSP.plugin.core.typing import List, Literal, NotRequired, Tuple, TypedDict, Union


class TypescriptVersionNotificationParams(TypedDict):
    version: str
    source: Union[Literal['bundled'], Literal['user-setting'], Literal['workspace']]


class ApplyRefactoringInteractiveRefactorArguments(TypedDict):
    targetFile: str  # noqa: N815


class ApplyRefactoringArgument(TypedDict):
    file: str
    action: str
    interactiveRefactorArguments: NotRequired[ApplyRefactoringInteractiveRefactorArguments]  # noqa: N815


class ApplyRefactoringCommand(TypedDict):
    command: str
    arguments: Tuple[ApplyRefactoringArgument]


class ShowReferencesCommand(TypedDict):
    command: str
    arguments: Tuple[str, Position, List[Location]]

