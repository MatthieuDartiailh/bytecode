import typing as t
from types import FunctionType, ModuleType

from function import FunctionDiscovery
from module import ModuleWatchdog

from bytecode import Bytecode


class FunctionCollector(ModuleWatchdog):
    def after_import(self, module):
        # type: (ModuleType) -> None
        discovery = FunctionDiscovery(module)
        for fname, f in discovery.items():
            function = t.cast(FunctionType, f)
            try:
                function.__code__ = Bytecode.from_code(function.__code__).to_code()
            except Exception:
                print("Failed to recompile %s" % fname)
                raise


print("Collecting functions")
FunctionCollector.install()
