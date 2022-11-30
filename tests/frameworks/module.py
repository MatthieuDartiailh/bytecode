import sys
from importlib.abc import Loader
from importlib.machinery import ModuleSpec
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, Optional, Set, Union, cast


def origin(module):
    # type: (ModuleType) -> str
    """Get the origin source file of the module."""
    try:
        assert module.__file__ is not None
        orig = str(Path(module.__file__).resolve())  # type: ignore[type-var]
    except (AttributeError, TypeError):
        # Module is probably only partially initialised, so we look at its
        # spec instead
        try:
            orig = str(Path(module.__spec__.origin).resolve())  # type: ignore
        except (AttributeError, ValueError, TypeError):
            orig = None

    if orig is not None and Path(orig).is_file():
        if orig.endswith(".pyc"):
            orig = orig[:-1]
        return orig

    return "<unknown origin>"


def find_loader(fullname):
    # type: (str) -> Optional[Loader]
    return getattr(find_spec(fullname), "loader", None)


class _ImportHookChainedLoader(Loader):
    def __init__(self, loader):
        # type: (Loader) -> None
        self.loader = loader
        self.callbacks = {}  # type: Dict[Any, Callable[[ModuleType], None]]

        # DEV: load_module is deprecated so we define it at runtime if also
        # defined by the default loader. We also check and define for the
        # methods that are supposed to replace the load_module functionality.
        if hasattr(loader, "load_module"):
            self.load_module = self._load_module  # type: ignore[assignment]
        if hasattr(loader, "create_module"):
            self.create_module = self._create_module  # type: ignore[assignment]
        if hasattr(loader, "exec_module"):
            self.exec_module = self._exec_module  # type: ignore[assignment]

    def __getattribute__(self, name):
        if name == "__class__":
            # Make isinstance believe that self is also an instance of
            # type(self.loader). This is required, e.g. by some tools, like
            # slotscheck, that can handle known loaders only.
            return self.loader.__class__

        return super(_ImportHookChainedLoader, self).__getattribute__(name)

    def __getattr__(self, name):
        # Proxy any other attribute access to the underlying loader.
        return getattr(self.loader, name)

    def add_callback(self, key, callback):
        # type: (Any, Callable[[ModuleType], None]) -> None
        self.callbacks[key] = callback

    def _load_module(self, fullname):
        # type: (str) -> ModuleType
        module = self.loader.load_module(fullname)
        for callback in self.callbacks.values():
            callback(module)

        return module

    def _create_module(self, spec):
        return self.loader.create_module(spec)

    def _exec_module(self, module):
        self.loader.exec_module(module)
        for callback in self.callbacks.values():
            callback(module)


class ModuleWatchdog:
    """Module watchdog.
    Replace the standard ``sys.modules`` dictionary to detect when modules are
    loaded/unloaded. This is also responsible for triggering any registered
    import hooks.
    Subclasses might customize the default behavior by overriding the
    ``after_import`` method, which is triggered on every module import, once
    the subclass is installed.
    """

    _instance = None  # type: Optional[ModuleWatchdog]

    def __init__(self):
        # type: () -> None
        self._finding = set()  # type: Set[str]

    def _add_to_meta_path(self):
        # type: () -> None
        sys.meta_path.insert(0, self)  # type: ignore[arg-type]

    @classmethod
    def _find_in_meta_path(cls):
        # type: () -> Optional[int]
        for i, meta_path in enumerate(sys.meta_path):
            if type(meta_path) is cls:
                return i
        return None

    @classmethod
    def _remove_from_meta_path(cls):
        # type: () -> None
        i = cls._find_in_meta_path()
        if i is not None:
            sys.meta_path.pop(i)

    def after_import(self, module):
        raise NotImplementedError()

    def find_module(self, fullname, path=None):
        # type: (str, Optional[str]) -> Union[ModuleWatchdog, _ImportHookChainedLoader, None]
        if fullname in self._finding:
            return None

        self._finding.add(fullname)

        try:
            loader = find_loader(fullname)
            if loader is not None:
                if not isinstance(loader, _ImportHookChainedLoader):
                    loader = _ImportHookChainedLoader(loader)

                loader.add_callback(type(self), self.after_import)

                return loader

        finally:
            self._finding.remove(fullname)

        return None

    def find_spec(self, fullname, path=None, target=None):
        # type: (str, Optional[str], Optional[ModuleType]) -> Optional[ModuleSpec]
        if fullname in self._finding:
            return None

        self._finding.add(fullname)

        try:
            spec = find_spec(fullname)
            if spec is None:
                return None

            loader = getattr(spec, "loader", None)

            if loader is not None:
                if not isinstance(loader, _ImportHookChainedLoader):
                    spec.loader = _ImportHookChainedLoader(loader)

                cast(_ImportHookChainedLoader, spec.loader).add_callback(
                    type(self), self.after_import
                )

            return spec

        finally:
            self._finding.remove(fullname)

    @classmethod
    def _check_installed(cls):
        # type: () -> None
        if not cls.is_installed():
            raise RuntimeError("%s is not installed" % cls.__name__)

    @classmethod
    def install(cls):
        # type: () -> None
        """Install the module watchdog."""
        if cls.is_installed():
            raise RuntimeError("%s is already installed" % cls.__name__)

        cls._instance = cls()
        cls._instance._add_to_meta_path()

    @classmethod
    def is_installed(cls):
        """Check whether this module watchdog class is installed."""
        return cls._instance is not None and type(cls._instance) is cls

    @classmethod
    def uninstall(cls):
        # type: () -> None
        """Uninstall the module watchdog.
        This will uninstall only the most recently installed instance of this
        class.
        """
        cls._check_installed()
        cls._remove_from_meta_path()
