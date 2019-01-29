from pathlib import PurePath
import inotify.adapters
import os.path
import glob
import math
import re

InotifyWatcherGlob = 0
InotifyWatcherFolder = 1
InotifyWatcherParent = 2
InotifyWatcherChild = 3

EventCreate = 0
EventUpdate = 1
EventRemove = 2

EventFile = 0
EventFolder = 1

def glob_root_folder ( pattern ):
    folders = pattern.split( os.sep )

    roots = []

    for folder in folders:
        if re.search( r'[*|!()]', folder ):
            break

        roots.append( folder )

    return os.sep.join( roots )

def is_glob ( pattern ):
    folders = pattern.split( os.sep )

    return any( re.search( r'[*|!()]', folder ) for folder in folders )



def glob_recursive_level ( pattern ):
    """
    Returns how many subfolders we would need to watch counting from the root folder, to be able to 
    receive all events for all the files within this pattern

    >>> glob_recursive_level( '/some/path' )
    0
    >>> glob_recursive_level( '/some/path/*.js' )
    0
    >>> glob_recursive_level( '/some/path/A*/*.js' )
    1
    >>> glob_recursive_level( '/some/path/A*/*B/*.js' )
    2
    >>> glob_recursive_level( '/some/path/A*/**/*B/*.js' )
    math.inf

    """
    folders = pattern.split( os.sep )

    level = 0

    for folder in folders:
        if level == 0 and not re.search( r'[*|!()]', folder ):
            continue

        if folder == '**':
            return math.inf
        
        level += 1

    # level is number of path segments after the first segment with special characters (including that first one)
    # But we don't want the first one, so we subtract 1 (but are careful to never go beneath 0
    return max( level - 1, 0 )

from collections import Counter

class InotifyWatcher:
    def __init__ ( self, glob, id = None, type = InotifyWatcherGlob, parent = None, children = None, recursive = 0 ):
        self.glob = glob
        self.id = id
        self.type = type
        self.parent = parent
        self.recursive = recursive
        self.children = children or []
    
    def __repr__ ( self ):
        return "<InotifyWatcher \n\tglob: %s \n\tid: %s \n\ttype: %s \n\tparent: %s\n\trecursive: %s\n\tchildren: %s\n>" % ( self.glob, self.id, self.type, self.parent, self.recursive, self.children )

class BetterInotify:
    def __init__ ( self, logger = None ):
        # Dictionary matching a path/glob to a watcher instance
        self.watchers = dict()
        # Dictionary matching an id to a watcher instance
        self.watchers_id = dict()
        
        self.counter = 0

        self.watchers_cache = Counter()

        self.inotify = inotify.adapters.Inotify()

        self.debug = False

        self.logger = logger

    def _debug ( self, *msg ):
        if self.debug:
            print( *msg )

    def _create_watcher ( self, watcher ):
        watcher.id = self.counter

        self.counter += 1

        self.watchers_id[ watcher.id ] = watcher
        
        if watcher.glob not in self.watchers:
            self.watchers[ watcher.glob ] = [ watcher ]
        else:
            self.watchers[ watcher.glob ].append( watcher )

        # By default every watcher added by the user is marked as a glob
        # For performance reasons, we can simply test if the path provided is indeed a glob or a regular file/folder
        if watcher.type == InotifyWatcherGlob:
            if is_glob( watcher.glob ):
                # When it is a glob, we need to determine the root of the glob expression (the prefix of the path that has no special glob syntax)
                # And create a regular watcher for that path
                child = self._create_watcher( InotifyWatcher( 
                    glob_root_folder( watcher.glob ), 
                    type = InotifyWatcherFolder, 
                    parent = watcher.id, 
                    recursive = glob_recursive_level( watcher.glob ) 
                ) )

                watcher.children.append( child.id )
            else:
                watcher.type = InotifyWatcherFolder

        exists = True

        # We cannot watch a folder/file that does not exists (the inotify lib throws an error)
        # So in that case what we do is create a watcher on the parent folder
        # And do so recursively until we find one folder that exists, and mark it as InotifyWatcherParent
        # This type of watcher does not emit events to the user, but rather waits for a specific child 
        # to be created, then creates a watcher for that child and kills itself
        if watcher.type == InotifyWatcherFolder or watcher.type == InotifyWatcherParent:
            # TODO Optimization: Check if the folder is already being watched and simply link them somehow, instead of creating a new watcher
            if not os.path.exists( watcher.glob ):
                child = self._create_watcher( InotifyWatcher( 
                    os.path.dirname( watcher.glob ), 
                    type = InotifyWatcherParent, 
                    parent = watcher.id,
                ) )

                watcher.children.append( child.id )

                exists = False
        
        if watcher.type == InotifyWatcherParent and exists:
            self._add_watch_native( watcher.glob )
        
        if exists and ( watcher.type == InotifyWatcherFolder or watcher.type == InotifyWatcherChild ):
            self._add_watch_native( watcher.glob )
                
            if watcher.recursive:
                # TODO Optimization: When the parent of watcher is a glob, do a partial glob test to see what childpaths are worth watching
                for childpath in glob.glob( os.path.join( watcher.glob, "*/" ) ):
                    # We want the folder name, but glob returns the folders with a trailing "/"
                    # Therefore, calling os.path.basename( childpath ) returns everything after the LAST "/"
                    # Which in our case would always be empty. Calling dirname first removes that trailing "/" and so
                    # basename now returns the correct value
                    childname = os.path.basename( os.path.dirname( childpath ) )

                    child = self._create_watcher( InotifyWatcher( 
                        os.path.join( watcher.glob, childname ), 
                        type = InotifyWatcherChild, 
                        parent = watcher.id,
                        recursive = max( watcher.recursive - 1, 0 )
                    ) )

                    watcher.children.append( child.id )

        return watcher

    def add_watch ( self, glob ):
        watcher = self._create_watcher( InotifyWatcher( glob ) )

        return watcher.id

    def remove_watch ( self, id, propagate = True ):
        if id in self.watchers_id:
            watcher = self.watchers_id[ id ]

            del self.watchers_id[ watcher.id ]

            self.watchers[ watcher.glob ].remove( watcher )

            if not self.watchers[ watcher.glob ]:
                del self.watchers[ watcher.glob ]

            if watcher.parent != None and watcher.parent in self.watchers_id:
                self.watchers_id[ watcher.parent ].children.remove( watcher.id )

            if propagate:
                for child in watcher.children:
                    self.remove_watch( child )

                if ( watcher.type == InotifyWatcherFolder or watcher.type == InotifyWatcherParent ) and watcher.parent != None:
                    self.remove_watch( watcher.parent )

    def _add_watch_native ( self, folder ):
        self._debug( 'WATCHING', folder )

        self.watchers_cache[ folder ] += 1

        if self.watchers_cache[ folder ] == 1:
            self.inotify.add_watch( folder )        
    
    def _remove_watch_native ( self, folder, superficial = False ):
        self._debug( 'REMOVING WATCHING', folder, superficial )

        self.watchers_cache[ folder ] -= 1

        if self.watchers_cache[ folder ] == 0:
            del self.watchers_cache[ folder ]

            # The Pynotify library has a bug in that it does not propagate the value of superficial to other functions,
            # There are multiple issues open reporting the situation but so far it has not been fixed.
            # Therefore when the value is different from the default (False) we copy-pasted the code, fixed it, and run it instead of calling the function
            if superficial:
                wd = self.inotify._Inotify__watches.get( folder )

                if wd is None:
                    return

                del self.inotify._Inotify__watches[ folder ]

                del self.inotify._Inotify__watches_r[ wd ]
            else:
                self.inotify.remove_watch( folder, superficial = superficial )

    def _get_event_action ( self, type_names ):
        if 'IN_CREATE' in type_names or 'IN_MOVED_TO' in type_names:
            return EventCreate
        elif 'IN_DELETE' in type_names or 'IN_MOVED_FROM' in type_names or 'IN_DELETE_SELF' in type_names:
            return EventRemove
        elif 'IN_MODIFY' in type_names:
            return EventUpdate
        else:
            return None

    def _get_event_type ( self, type_names ):
        if 'IN_ISDIR' in type_names or 'IN_DELETE_SELF' in type_names:
            return EventFolder
        else:
            return EventFile

    def _get_flags ( self, var, *values ):
        return [ v == var for v in values ]

    def _transform ( self, leaf, event ):
        """
        Transforms an event from Pynotify. Returns None if the event it received does not apply 
        (for example, the file is inside a watched folder but does not match the glob pattern)
        """
        if event == None:
            return None

        ( type_names, path, filename ) = event
        
        action = self._get_event_action( type_names )
        type = self._get_event_type( type_names )

        if leaf.type == InotifyWatcherParent:
            return None
        
        root = leaf

        while root.type != InotifyWatcherGlob and root.parent != None:
            root = self.watchers_id[ root.parent ]

        filepath = os.path.join( path, filename )

        # print( root.glob, root.type == InotifyWatcherGlob, filepath, PurePath( filepath ).match( root.glob ) )
        if root.type == InotifyWatcherGlob and not PurePath( filepath ).match( root.glob ):
            return None

        return ( root.id, action, type, filepath )
    
    def listen ( self, ignore_missing_new_folders = False, **kwargs ):
        for event in self.inotify.event_gen(**kwargs):
            if event is not None:
                ( header, type_names, path, filename ) = event

                # Every folder we're listening should have a watcher attached, if not it's best to just skip the event
                if path not in self.watchers:
                    self._debug( f"Path '{ path }' not found in watchers" )
                    continue

                # POSSIBLE CASES:
                # (x) means emit event
                # - InotifyWatcherParent CREATE parent path: Remove watcher and add parent native watcher
                # - InotifyWatcherParent REMOVE self path: Create another parent watcher and add parent native watcher
                # - InotifyWatcherChild | InotifyWatcherFolder CREATE child folder: Create another InotifyWatcherChild and add native watcher (x)
                # - InotifyWatcherChild REMOVE self folder: Remove watcher (x)
                # - InotifyWatcherFolder REMOVE self folder: Create parent watcher (x)

                is_create, is_remove, is_update = self._get_flags( self._get_event_action( type_names ), EventCreate, EventRemove, EventUpdate )
                is_folder, is_file = self._get_flags( self._get_event_type( type_names ), EventFolder, EventFile )

                if not is_remove and not is_create and not is_update:
                    self._debug( f"Ignored event type {type_names} {is_remove}" )
                    continue

                self._debug( type_names, path, filename, '\n' )

                # Set a boolean flag to avoid logging the same event more than once
                logged = False

                for watcher in self.watchers[ path ]:
                    t_watcher, t_path, t_filename = watcher, path, filename

                    if watcher.type == InotifyWatcherParent:
                        parent_watcher = self.watchers_id[ watcher.parent ]

                        if is_create and os.path.join( path, filename ) == parent_watcher.glob:
                            self.remove_watch( watcher.id, propagate = False )

                            self._remove_watch_native( watcher.glob )

                            self._add_watch_native( parent_watcher.glob )

                            t_watcher, t_path, t_filename = parent_watcher, os.path.join( path, filename ), ''
                        elif is_remove and not filename:
                            child = self._create_watcher( InotifyWatcher( 
                                os.path.dirname( watcher.glob ), 
                                type = InotifyWatcherParent, 
                                parent = watcher.id,
                            ) )

                            watcher.children.append( child.id )

                            self._remove_watch_native( watcher.glob, superficial = True )
                    elif watcher.type == InotifyWatcherChild: # or 
                        if is_folder and is_create and watcher.recursive > 0:
                            child = self._create_watcher( InotifyWatcher( 
                                os.path.join( watcher.glob, filename ), 
                                type = InotifyWatcherChild, 
                                parent = watcher.id,
                                recursive = max( watcher.recursive - 1, 0 )
                            ) )

                            watcher.children.append( child.id )

                            self._add_watch_native( child.glob )
                        elif is_remove and not filename:
                            self.remove_watch( watcher.id, propagate = False )

                            self._remove_watch_native( watcher.glob, superficial = True )

                            t_watcher, t_path, t_filename = self.watchers_id[ watcher.parent ], os.path.dirname( path ), os.path.basename( path )
                    elif watcher.type == InotifyWatcherFolder:
                        if is_folder and is_create and watcher.recursive > 0:
                            child = self._create_watcher( InotifyWatcher( 
                                os.path.join( watcher.glob, filename ), 
                                type = InotifyWatcherChild, 
                                parent = watcher.id,
                                recursive = max( watcher.recursive - 1, 0 )
                            ) )

                            watcher.children.append( child.id )

                            self._add_watch_native( child.glob )
                        elif is_remove and not filename:
                            child = self._create_watcher( InotifyWatcher( 
                                os.path.dirname( watcher.glob ), 
                                type = InotifyWatcherParent, 
                                parent = watcher.id,
                            ) )

                            watcher.children.append( child.id )

                            self._remove_watch_native( watcher.glob, superficial = True )

                    event = self._transform( t_watcher, ( type_names, t_path, t_filename ) )

                    if event != None:
                        if not logged and self.logger:
                            self.logger.log( event_name( event[ 1 ] ), type_name( event[ 2 ] ), event[ 3 ] )
                            
                            logged = True

                        yield event
            else:
                # When the event is None, always emit it
                yield event

def event_name ( event ):
    if event ==  EventCreate:
        return "create"
    elif event == EventUpdate:
        return "update"
    elif event == EventRemove:
        return "remove"
    else: return None

def type_name ( type ):
    if type == EventFile:
        return "file"
    elif type == EventFolder:
        return "folder"
    else: return None
