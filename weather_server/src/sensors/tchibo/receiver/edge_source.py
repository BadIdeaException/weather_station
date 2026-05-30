from typing import Protocol, TypeAlias
from collections.abc import Callable

EdgeCallback: TypeAlias = Callable[[float, int, "EdgeSource"], None]

class EdgeSource(Protocol):
    @property
    def on_rising(self) -> EdgeCallback | None: ...

    @on_rising.setter
    def on_rising(self, cb: EdgeCallback | None) -> None: ...

    @property
    def on_falling(self) -> EdgeCallback | None: ...

    @on_falling.setter
    def on_falling(self, cb: EdgeCallback | None) -> None: ...

    def read(self) -> int: ...