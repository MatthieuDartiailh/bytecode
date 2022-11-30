import dis
import io
import sys
import typing as t
from types import FunctionType, ModuleType

from function import FunctionDiscovery  # type: ignore
from module import ModuleWatchdog  # type: ignore

from bytecode import Bytecode, ControlFlowGraph


class FunctionCollector(ModuleWatchdog):
    def after_import(self, module):
        # type: (ModuleType) -> None
        discovery = FunctionDiscovery(module)
        for fname, f in discovery.items():
            function = t.cast(FunctionType, f)
            try:
                byt = Bytecode.from_code(function.__code__)
                cfg = ControlFlowGraph.from_bytecode(byt)
                new = cfg.to_code()
                # Check we can still disassemble the code
                dis.dis(new, file=io.StringIO())
            except Exception:
                print("Failed to recompile %s" % fname)
                dis.dis(function)
                raise
            else:
                function.__code__ = new


print("Collecting functions")
FunctionCollector.install()
