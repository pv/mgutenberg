import pygtk
pygtk.require('2.0')
import gtk
import gobject
from gettext import gettext as _

import guithread
from guithread import *

__all__ = ['gtk', 'gobject', 'MAEMO', 'Window', 'StackableWindow',
           'TextView', 'AppBase', 'FileChooserDialog', '_']

try:
    import hildon
    MAEMO = True
    AppBase = hildon.Program
    Window = hildon.Window
    StackableWindow = hildon.StackableWindow
    TextView = hildon.TextView
    FileChooserDialog = hildon.FileChooserDialog
    __all__.append('hildon')
except ImportError:
    MAEMO = False
    AppBase = object
    Window = gtk.Window
    StackableWindow = gtk.Window
    TextView = gtk.TextView
    FileChooserDialog = gtk.FileChooserDialog

__all__.extend(guithread.__all__)
