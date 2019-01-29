import BetterInotify
import os

class ShellExecutor:
    def run ( actions, variables ):
        pass

class PythonExecutor:
    def run ( actions, variables ):
        pass

class PowershellExecutor:
    def run ( actions, variables ):
        pass
        
class Inotifile:
    def __init__ ( self, executors, watchers ):
        self.executors = executors
        self.watchers = watchers
    
    def create_variables ( self, event ):
        ( id, action, type, filepath ) = event

        return {
            FILE: filepath,
            FILENAME: os.path.basename( filepath )
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

                    if watcher.test( filepath, [ BetterInotify.event_name( action ), BetterInotify.event_name( type ) ] ):
                        print( '>>>', event )

        
