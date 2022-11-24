import dis
import io
import sys
import typing as t
from types import FunctionType, ModuleType

from function import FunctionDiscovery
from module import ModuleWatchdog

from bytecode import Bytecode, ControlFlowGraph


class FunctionCollector(ModuleWatchdog):
    def after_import(self, module):
        # type: (ModuleType) -> None
        discovery = FunctionDiscovery(module)
        for fname, f in discovery.items():
            function = t.cast(FunctionType, f)
            try:
                byt = Bytecode.from_code(
                    function.__code__
                )
                cfg = ControlFlowGraph.from_bytecode(byt)
                new = cfg.to_code()
                # Check we can still disassemble the code
                dis.dis(new, file=io.StringIO())
                # If the code does not contain dead code, check we use safe values
                # for the stack (stacksize and exception table)
                # In the presence of dead code we cannot reproduce CPython caluclation
                # for the dead portions
                if not cfg.get_dead_blocks():
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
