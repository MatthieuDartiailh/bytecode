import dis
import io
import sys
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
                new = Bytecode.from_code(function.__code__).to_code()
                # Check we can still disassemble the code
                dis.dis(new, file=io.StringIO())
                # Check we use safe values for the stack (stacksize and exception table)
                # (avoid stack overflow and segfaults)
                assert new.co_stacksize == function.__code__.co_stacksize
                if sys.version_info >= (3, 11):
                    assert new.co_exceptiontable == function.__code__.co_exceptiontable
            except Exception:
                print("Failed to recompile %s" % fname)
                dis.dis(function)
                raise
            else:
                function.__code__ = new


print("Collecting functions")
FunctionCollector.install()
