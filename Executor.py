import BetterInotify
import Logger
import subprocess
import base64
import sys
import os

class Executor:
    def escape ( self, string, quote = "'" ):
        string = string.replace( "\\", "\\\\" ).replace( quote, f"\\{quote}" )

        return f"{quote}{string}{quote}"

class ShellExecutor(Executor):
    def inject ( self, variables ):
        return [ f'{key}={variables[key]}' for key in variables.keys() ]

    def run ( self, actions, variables ):
        command = '\n'.join( self.inject( variables ) + actions )
        
        subprocess.run( [ '/bin/sh' ], input = command, stdout = sys.stdout, encoding = 'ascii' )

class PythonExecutor(Executor):
    def run ( self, actions, variables ):
        exec( '\n'.join( actions ), variables )

class PowershellExecutor(Executor):
    def inject ( self, variables ):
        return [ f'${key}={self.escape(variables[key])}' for key in variables.keys() ]

    def run_script ( self, script ):
        command = base64.b64encode( 
            script.encode('UTF-16LE') 
        ).decode( 'ascii' )

        os.system( f'pwsh-preview -ec {command}' )


    def run ( self, actions, variables ):
        self.run_script( '\n'.join( self.inject( variables ) + actions ) )

class CSharpExecutor(PowershellExecutor):
    def inject ( self, variables ):
        quote = '"'

        return [ f'String {key} = {self.escape(variables[key], quote)};' for key in variables.keys() ]

    def run ( self, actions, variables ):
        variables = self.inject( variables )

        source = """
        $assemblies=(
            "System", "System.Console"
        )

        $source=@"
        using System;
        
        #pragma warning disable CS0219
        namespace INotify {
            public static class App {
                public static void Main(){
                    """ + '\n'.join( variables ) + """
                    """ + '\n'.join( actions ) + """
                }
            }
        }
"@

        Add-Type -ReferencedAssemblies $assemblies -TypeDefinition $source -Language CSharp -IgnoreWarnings

        [INotify.App]::Main()
        """

        self.run_script( source )
        

class NodeExecutor(Executor):
    def inject ( self, variables ):
        return [ f'var {key}={self.escape(variables[key])}' for key in variables.keys() ]

    def run ( self, actions, variables ):
        command = '\n'.join( self.inject( variables ) + actions )
        
        subprocess.run( [ '/usr/bin/env', 'node' ], input = command, stdout = sys.stdout, encoding = 'ascii' )

        
class Inotifile:
    def __init__ ( self, executors, watchers ):
        self.executors = executors
        self.watchers = watchers
    
    def create_variables ( self, event ):
        ( id, action, type, filepath ) = event

        return {
            'FILE': filepath,
            'EXTNAME': os.path.splitext( filepath )[ 1 ],
            'FILENAME': os.path.basename( filepath ),
            'DIRNAME': os.path.dirname( filepath ),
            'ACTION': BetterInotify.event_name( action ),
            'TYPE': BetterInotify.type_name( type )
        }

    def start ( self ):
        inotify = BetterInotify.BetterInotify( logger = Logger.Logger() )

        watchers_ids = dict()

        # Add the patterns from the Inotify file to the watcher
        for watcher in self.watchers:
            for folder in watcher.patterns:
                id = inotify.add_watch( folder )

                watchers_ids[ id ] = watcher

        if inotify.logger: inotify.logger.flush()

        for event in inotify.listen():
            if event != None: 
                ( id, action, type, filepath ) = event

                if id in watchers_ids:
                    watcher = watchers_ids[ id ]

                    if watcher.test( filepath, [ BetterInotify.event_name( action ), BetterInotify.type_name( type ) ] ):
                        # self.logger.log( BetterInotify.event_name( action ), BetterInotify.type_name( type ), filepath )

                        variables = self.create_variables( event )

                        executor = self.executors[ watcher.executor or 'shell' ]

                        executor.run( watcher.actions, variables )
            
            if inotify.logger: inotify.logger.flush()

        
