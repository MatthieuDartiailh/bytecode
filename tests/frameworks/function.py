from collections import deque
from collections.abc import Iterator
from os.path import abspath
from types import FunctionType, ModuleType
from typing import Any, Dict, Optional, Protocol, Tuple, Type, Union, cast

from module import origin  # type: ignore

FunctionContainerType = Union[
    type, property, classmethod, staticmethod, Tuple, ModuleType
]

ContainerKey = Union[str, int, Type[staticmethod], Type[classmethod]]

CONTAINER_TYPES = (type, property, classmethod, staticmethod)


def set_cell_contents(cell, contents):  # type: ignore[misc]
    cell.cell_contents = contents


class FullyNamed(Protocol):
    """A fully named object."""

    __name__ = None  # type: Optional[str]
    __fullname__ = None  # type: Optional[str]


class FullyNamedFunction(FullyNamed):
    """A fully named function object."""

    def __call__(self, *args, **kwargs):
        pass


class ContainerIterator(Iterator, FullyNamedFunction):
    """Wrapper around different types of function containers.

    A container comes with an origin, i.e. a parent container and a position
    within it in the form of a key.
    """

    def __init__(
        self,
        container,  # type: FunctionContainerType
        origin=None,  # type: Optional[Union[Tuple[ContainerIterator, ContainerKey], Tuple[FullyNamedFunction, str]]]
    ):
        # type: (...) -> None
        if isinstance(container, (type, ModuleType)):
            self._iter = iter(container.__dict__.items())
            self.__name__ = container.__name__

        elif isinstance(container, tuple):
            self._iter = iter(enumerate(_.cell_contents for _ in container))  # type: ignore[arg-type]
            self.__name__ = "<locals>"

        elif isinstance(container, property):
            self._iter = iter(
                (m, getattr(container, a))
                for m, a in {
                    ("getter", "fget"),
                    ("setter", "fset"),
                    ("deleter", "fdel"),
                }
            )
            assert container.fget is not None
            self.__name__ = container.fget.__name__

        elif isinstance(container, (classmethod, staticmethod)):
            self._iter = iter([(type(container), container.__func__)])  # type: ignore[list-item]
            self.__name__ = None

        else:
            raise TypeError("Unsupported container type: %s", type(container))

        self._container = container

        if origin is not None and origin[0].__fullname__ is not None:
            origin_fullname = origin[0].__fullname__
            self.__fullname__ = (
                ".".join((origin_fullname, self.__name__))
                if self.__name__
                else origin_fullname
            )
        else:
            self.__fullname__ = self.__name__

    def __iter__(self):
        # type: () -> Iterator[Tuple[ContainerKey, Any]]
        return self._iter

    def __next__(self):
        # type: () -> Tuple[ContainerKey, Any]
        return next(self._iter)

    next = __next__


def _collect_functions(module):
    # type: (ModuleType) -> Dict[str, FullyNamedFunction]
    """Collect functions from a given module."""
    assert isinstance(module, ModuleType)

    path = origin(module)
    containers = deque([ContainerIterator(module)])
    functions = {}
    seen_containers = set()
    seen_functions = set()

    while containers:
        c = containers.pop()

        if id(c._container) in seen_containers:
            continue
        seen_containers.add(id(c._container))

        for k, o in c:
            code = getattr(o, "__code__", None) if isinstance(o, FunctionType) else None
            if code is not None and abspath(code.co_filename) == path:
                if o not in seen_functions:
                    seen_functions.add(o)
                    o = cast(FullyNamedFunction, o)
                    o.__fullname__ = (
                        ".".join((c.__fullname__, o.__name__))
                        if c.__fullname__
                        else o.__name__
                    )

                for name in (k, o.__name__) if isinstance(k, str) else (o.__name__,):
                    fullname = (
                        ".".join((c.__fullname__, name)) if c.__fullname__ else name
                    )
                    functions[fullname] = o

                try:
                    if o.__closure__:
                        containers.append(
                            ContainerIterator(o.__closure__, origin=(o, "<locals>"))
                        )
                except AttributeError:
                    pass

            elif isinstance(o, CONTAINER_TYPES):
                if isinstance(o, property) and not isinstance(o.fget, FunctionType):
                    continue
                containers.append(ContainerIterator(o, origin=(c, k)))

    return functions


class FunctionDiscovery(dict):
    """Discover all function objects in a module."""

    def __init__(self, module):
        # type: (ModuleType) -> None
        super(FunctionDiscovery, self).__init__()
        self._module = module

        functions = _collect_functions(module)
        seen_functions = set()

        for fname, function in functions.items():
            self[fname] = function
            seen_functions.add(function)
