import sys

def styled ( txt, style ): return f"\033[{style}m{txt}\033[0m"
def fgRed ( txt ): return styled( txt, 31 )
def fgGreen ( txt ): return styled( txt, 32 )
def fgYellow ( txt ): return styled( txt, 33 )
def fgBlue ( txt ): return styled( txt, 34 )
def fgMagenta ( txt ): return styled( txt, 35 )
def fgCyan ( txt ): return styled( txt, 36 )
def fgWhite ( txt ): return styled( txt, 37 )
def fgGray ( txt ): return styled( txt, 90 )
def eraseLastLine (): print( "\033[A\33[2K\r", end = '' )
def stripAnsi ( txt ): return re.sub( r'\033+\[[0-9]+m', '', txt )

class Logger:
    def __init__ ( self, file = sys.stderr ):
        self.file = file

    def color_action ( self, action ):
        if action == 'REMOVE':
            return fgRed( action )
        elif action == 'CREATE':
            return fgBlue( action )
        elif action == 'UPDATE':
            return fgGreen( action )
        else: return action

    def color_type ( self, type ):
        if type == 'FOLDER':
            return fgCyan( type )
        elif type == 'FILE':
            return fgGray( type )
        else: return type

    def log ( self, action, type, filepath ):
        if self.file == sys.stderr or self.file == sys.stdout:
            action = self.color_action( action.upper() )
            type = self.color_type( type.upper() )
        
        self.file.write( f'{action} {type} {filepath}\n' )
