import atexit
import dis
import io
from datetime import timedelta
from time import monotonic as time
from types import CodeType, ModuleType

from module import BaseModuleWatchdog  # type: ignore

from bytecode import Bytecode, ControlFlowGraph

_original_exec = exec


class ModuleCodeCollector(BaseModuleWatchdog):
    def __init__(self):
        super().__init__()

        # Count how many code objects we've recompiled
        self.count = 0
        self.stopwatch = 0

        # Replace the built-in exec function with our own in the pytest globals
        try:
            import _pytest.assertion.rewrite as par

            par.exec = self._exec
        except ImportError:
            pass

    def transform(
        self, code: CodeType, _module: ModuleType, root: bool = True
    ) -> CodeType:
        # Round-trip the code object through the library
        try:
            start = time()

            abstract_code = Bytecode.from_code(code)

            for instr in abstract_code:
                try:
                    if isinstance(instr.arg, CodeType):
                        instr.arg = self.transform(instr.arg, _module, root=False)
                except AttributeError:
                    pass

            cfg = ControlFlowGraph.from_bytecode(abstract_code)

            recompiled_code = cfg.to_code()

            # Check we can still disassemble the code
            dis.dis(recompiled_code, file=io.StringIO())

            if root:
                # Only time the root code objects because of the recursion
                self.stopwatch += time() - start

            self.count += 1

            return recompiled_code
        except Exception:
            print(f"Failed to recompile {code} from {_module}")
            dis.dis(code)
            raise

    def after_import(self, _module: ModuleType) -> None:
        pass

    def _exec(self, _object, _globals=None, _locals=None, **kwargs):
        # The pytest module loader doesn't implement a get_code method so we
        # need to intercept the loading of test modules by wrapping around the
        # exec built-in function.
        new_object = (
            self.transform(_object, None)
            if isinstance(_object, CodeType) and _object.co_name == "<module>"
            else _object
        )

        # Execute the module before calling the after_import hook
        _original_exec(new_object, _globals, _locals, **kwargs)

    @classmethod
    def uninstall(cls) -> None:
        # Restore the original exec function
        try:
            import _pytest.assertion.rewrite as par

            par.exec = _original_exec
        except ImportError:
            pass

        # Proof of work
        print(
            f"Recompiled {cls._instance.count} code objects in {timedelta(seconds=cls._instance.stopwatch)}"
        )

        return super().uninstall()


print("Collecting module code objects")
ModuleCodeCollector.install()


@atexit.register
def _():
    ModuleCodeCollector.uninstall()
