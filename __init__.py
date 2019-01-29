import Executor
import Parser

executors = {
    'shell': Executor.ShellExecutor(),
    'python': Executor.PythonExecutor(),
    'pwsh': Executor.PowershellExecutor(),
    'csharp': Executor.CSharpExecutor(),
    'node': Executor.NodeExecutor()
}

watchers = Parser.file( './Inotifile' )

try:
    Executor.Inotifile( executors, watchers ).start()
except KeyboardInterrupt:
    print()

