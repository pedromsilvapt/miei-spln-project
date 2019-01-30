import re
import os

MODE_CONDITION = 0
MODE_ACTION = 1

def is_indented ( line ):
    return line.startswith( '\t' ) or line.startswith( '    ' )

def unindent ( line ):
    return re.sub( r'^(\t|    )', '', line )

def parse_inotifile_watcher ( line ):
    watcher = Watcher()

    # re.match always starts at the beginning of the string
    while True:
        match = re.match( r'^\[([^\]]*)\]\s*', line )

        if match:
            line = line[ len( match[ 0 ] ): ]

            conditions = re.split( r'\s+', match[ 1 ].strip() )

            # Adds multiple conditions
            watcher.conditions.append( conditions )
        else:
            break

    # re.search can find matches in the middle of the string
    # In this case since we have the dollar sign $ at the end of the pattern
    # We are forcing to only match at the end of the line
    match = re.search( r':\s*(\w+)\s*$', line )

    if match:
        watcher.executor = match[ 1 ]

        line = line[ :-len( match[ 0 ] ) ]

    patterns = re.split( r'\s+', line.strip() )

    watcher.patterns.extend( patterns )
    
    return watcher

def parse_inotifile ( content ):
    """
    Our parsing strategy is to consider two types of lines: unindented lines represent condition (the patter of files, the executor, etc...)
    Indented lines are added as actions to the last condition registered (if none is found, an exception is thrown)
    Lines starting with the hastag character (#) are treated as comments
    """

    mode = MODE_CONDITION

    watchers = []

    watcher = None

    for line in content.split( '\n' ):
        # Ignore empty lines and lines starting with a # as comments
        if not line.strip() or line.strip().startswith( '#' ): continue

        if mode == MODE_ACTION:
            if not is_indented( line ):
                mode = MODE_CONDITION

                watcher = None
            else:
                if not watcher:
                    raise Exception( 'Inotify actions should have a condition first.' )

                watcher.actions.append( unindent( line ) )

        if mode == MODE_CONDITION:
            watcher = parse_inotifile_watcher( line )

            watchers.append( watcher )

            mode = MODE_ACTION
            
    return watchers

def glob_root_folder ( pattern ):
    folders = pattern.split( os.sep )

    roots = []

    for folder in folders:
        if re.search( r'[*|!()]', folder ):
            break

        roots.append( folder )

    return os.sep.join( roots )

class Watcher:
    def __init__ ( self ):
        self.conditions = []
        self.patterns = []
        self.executor = None
        self.actions = []

    def folders ( self ):
        for pattern in self.patterns:
            yield glob_root_folder( pattern )

    def test ( self, filename, tags ):
        # Each condition must have at least one matching tag
        for condition in self.conditions:
            # So if all tags are a mismatch, the test is negative
            if all( [ tag not in tags for tag in condition ] ):
                return False

        return True

    def __repr__ ( self ):
        return "<Watcher \n\tconditions: %s \n\tpatterns: %s \n\texecutor: %s \n\tactions: %s>" % ( self.conditions, self.patterns, self.executor, self.actions )

def file ( name ):
    with open( name ) as f:
        return parse_inotifile( f.read() )
