import pygtk
pygtk.require('2.0')
import gtk
import gobject
from gettext import gettext as _

import guithread
from guithread import *

try:
    import hildon
    MAEMO = True
    AppBase = hildon.Program
    Window = hildon.Window
    StackableWindow = hildon.StackableWindow
    TextView = hildon.TextView
except ImportError:
    MAEMO = False
    AppBase = object
    Window = gtk.Window
    StackableWindow = gtk.Window
    TextView = gtk.TextView

__all__ = ['gtk', 'gobject', 'hildon', 'MAEMO', 'Window', 'StackableWindow',
           'TextView', 'AppBase', '_']
__all__.extend(guithread.__all__)
