import Executor
import Parser
import Logger
import getopt
import sys

executors = {
    'shell': Executor.ShellExecutor(),
    'python': Executor.PythonExecutor(),
    'pwsh': Executor.PowershellExecutor(),
    'csharp': Executor.CSharpExecutor(),
    'node': Executor.NodeExecutor()
}

options, args = getopt.getopt( sys.argv[1:], '', [ 'logger=' ] )
options = dict( options )

if len( args ) == 0:
    watchers = Parser.file( './Inotifile' )
else:
    watchers = Parser.file( args[ 0 ] )

try:
    logger = Logger.Logger( file = open( options[ '--logger' ], 'a' ) if '--logger' in options else sys.stderr )

    Executor.Inotifile( executors, watchers ).start( logger = logger )
except KeyboardInterrupt:
    print()

