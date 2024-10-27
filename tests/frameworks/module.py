import abc
import sys
import typing as t
from importlib._bootstrap import _init_module_attrs  # type: ignore
from importlib.abc import Loader
from importlib.machinery import ModuleSpec
from importlib.util import find_spec
from types import CodeType, ModuleType

TransformerType = t.Callable[[CodeType, ModuleType], CodeType]


def find_loader(fullname: str) -> t.Optional[Loader]:
    return getattr(find_spec(fullname), "loader", None)


def is_namespace_spec(spec: ModuleSpec) -> bool:
    return spec.origin is None and spec.submodule_search_locations is not None


class _ImportHookChainedLoader:
    def __init__(
        self, loader: t.Optional[Loader], spec: t.Optional[ModuleSpec] = None
    ) -> None:
        self.loader = loader
        self.spec = spec

        self.callbacks: t.Dict[t.Any, t.Callable[[ModuleType], None]] = {}
        self.transformers: t.Dict[t.Any, TransformerType] = {}

        # A missing loader is generally an indication of a namespace package.
        if loader is None or hasattr(loader, "create_module"):
            self.create_module = self._create_module
        if loader is None or hasattr(loader, "exec_module"):
            self.exec_module = self._exec_module

    def __getattr__(self, name):
        # Proxy any other attribute access to the underlying loader.
        return getattr(self.loader, name)

    def namespace_module(self, spec: ModuleSpec) -> ModuleType:
        module = ModuleType(spec.name)
        # Pretend that we do not have a loader (this would be self), to
        # allow _init_module_attrs to create the appropriate NamespaceLoader
        # for the namespace module.
        spec.loader = None

        _init_module_attrs(spec, module, override=True)

        # Chain the loaders
        self.loader = spec.loader
        module.__loader__ = spec.loader = self  # type: ignore[assignment]

        return module

    def add_callback(
        self, key: t.Any, callback: t.Callable[[ModuleType], None]
    ) -> None:
        self.callbacks[key] = callback

    def add_transformer(self, key: t.Any, transformer: TransformerType) -> None:
        self.transformers[key] = transformer

    def call_back(self, module: ModuleType) -> None:
        if module.__name__ == "pkg_resources":
            # DEV: pkg_resources support to prevent errors such as
            # NotImplementedError: Can't perform this operation for unregistered
            # loader type
            module.register_loader_type(
                _ImportHookChainedLoader, module.DefaultProvider
            )

        for callback in self.callbacks.values():
            callback(module)

    def load_module(self, fullname: str) -> t.Optional[ModuleType]:
        if self.loader is None:
            if self.spec is None:
                return None
            sys.modules[self.spec.name] = module = self.namespace_module(self.spec)
        else:
            module = self.loader.load_module(fullname)

        self.call_back(module)

        return module

    def _create_module(self, spec):
        if self.loader is not None:
            return self.loader.create_module(spec)

        if is_namespace_spec(spec):
            return self.namespace_module(spec)

        return None

    def _exec_module(self, module: ModuleType) -> None:
        _get_code = getattr(self.loader, "get_code", None)
        if _get_code is not None:

            def get_code(_loader, fullname):
                code = _get_code(fullname)

                for callback in self.transformers.values():
                    code = callback(code, module)

                return code

            self.loader.get_code = get_code.__get__(self.loader, type(self.loader))  # type: ignore[union-attr]

        if self.loader is None:
            spec = getattr(module, "__spec__", None)
            if spec is not None and is_namespace_spec(spec):
                sys.modules[spec.name] = module
        else:
            self.loader.exec_module(module)

        self.call_back(module)


class BaseModuleWatchdog:
    """Base module watchdog.

    Invokes ``after_import`` every time a new module is imported.
    """

    _instance: t.Optional["BaseModuleWatchdog"] = None

    def __init__(self) -> None:
        self._finding: t.Set[str] = set()

        # DEV: pkg_resources support to prevent errors such as
        # NotImplementedError: Can't perform this operation for unregistered
        pkg_resources = sys.modules.get("pkg_resources")
        if pkg_resources is not None:
            pkg_resources.register_loader_type(
                _ImportHookChainedLoader, pkg_resources.DefaultProvider
            )

    def _add_to_meta_path(self) -> None:
        sys.meta_path.insert(0, self)  # type: ignore[arg-type]

    @classmethod
    def _find_in_meta_path(cls) -> t.Optional[int]:
        for i, meta_path in enumerate(sys.meta_path):
            if type(meta_path) is cls:
                return i
        return None

    @classmethod
    def _remove_from_meta_path(cls) -> None:
        i = cls._find_in_meta_path()

        if i is None:
            raise RuntimeError("%s is not installed" % cls.__name__)

        sys.meta_path.pop(i)

    def after_import(self, module: ModuleType) -> None:
        raise NotImplementedError()

    def transform(self, code: CodeType, _module: ModuleType) -> CodeType:
        return code

    def find_module(
        self, fullname: str, path: t.Optional[str] = None
    ) -> t.Optional[Loader]:
        if fullname in self._finding:
            return None

        self._finding.add(fullname)

        try:
            original_loader = find_loader(fullname)
            if original_loader is not None:
                loader = (
                    _ImportHookChainedLoader(original_loader)
                    if not isinstance(original_loader, _ImportHookChainedLoader)
                    else original_loader
                )

                loader.add_callback(type(self), self.after_import)
                loader.add_transformer(type(self), self.transform)

                return t.cast(Loader, loader)

        finally:
            self._finding.remove(fullname)

        return None

    def find_spec(
        self,
        fullname: str,
        path: t.Optional[str] = None,
        target: t.Optional[ModuleType] = None,
    ) -> t.Optional[ModuleSpec]:
        if fullname in self._finding:
            return None

        self._finding.add(fullname)

        try:
            try:
                # Best effort
                spec = find_spec(fullname)
            except Exception:
                return None

            if spec is None:
                return None

            loader = getattr(spec, "loader", None)

            if not isinstance(loader, _ImportHookChainedLoader):
                spec.loader = t.cast(Loader, _ImportHookChainedLoader(loader, spec))

            t.cast(_ImportHookChainedLoader, spec.loader).add_callback(
                type(self), self.after_import
            )
            t.cast(_ImportHookChainedLoader, spec.loader).add_transformer(
                type(self), self.transform
            )

            return spec

        finally:
            self._finding.remove(fullname)

    @classmethod
    def _check_installed(cls) -> None:
        if not cls.is_installed():
            raise RuntimeError("%s is not installed" % cls.__name__)

    @classmethod
    def install(cls) -> None:
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
    def uninstall(cls) -> None:
        """Uninstall the module watchdog.

        This will uninstall only the most recently installed instance of this
        class.
        """
        cls._check_installed()
        cls._remove_from_meta_path()

        cls._instance = None
