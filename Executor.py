import BetterInotify
import subprocess
import base64
import sys
import os

class ShellExecutor:
    def inject ( self, variables ):
        return [ f'{key}={variables[key]}' for key in variables.keys() ]

    def run ( self, actions, variables ):
        command = '\n'.join( self.inject( variables ) + actions )
        
        subprocess.run( [ '/bin/sh' ], input = command, stdout = sys.stdout, encoding = 'ascii' )

class PythonExecutor:
    def run ( self, actions, variables ):
        exec( '\n'.join( actions ), variables )

class PowershellExecutor:
    def escape ( self, string ):
        string = string.replace( "\\", "\\\\" ).replace( "'", "\\'" )

        return f"'{string}'"

    def inject ( self, variables ):
        return [ f'${key}={self.escape(variables[key])}' for key in variables.keys() ]

    def run ( self, actions, variables ):
        command = base64.b64encode( 
            '\n'.join( self.inject( variables ) + actions ).encode('UTF-16LE') 
        ).decode( 'ascii' )

        os.system( f'pwsh-preview -ec {command}' )
        
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
        inotify = BetterInotify.BetterInotify()

        watchers_ids = dict()

        # Add the patterns from the Inotify file to the watcher
        for watcher in self.watchers:
            for folder in watcher.patterns:
                id = inotify.add_watch( folder )

                watchers_ids[ id ] = watcher

        for event in inotify.listen():
            if event != None: 
                ( id, action, type, filepath ) = event

                if id in watchers_ids:
                    watcher = watchers_ids[ id ]

                    if watcher.test( filepath, [ BetterInotify.event_name( action ), BetterInotify.type_name( type ) ] ):
                        variables = self.create_variables( event )

                        executor = self.executors[ watcher.executor or 'shell' ]

                        executor.run( watcher.actions, variables )

        
