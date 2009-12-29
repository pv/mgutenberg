import pygtk
pygtk.require('2.0')
import gtk
import gobject
from gettext import gettext as _

import guithread
from guithread import *

__all__ = ['gtk', 'gobject', 'MAEMO', 'Window', 'StackableWindow',
           'TextView', 'AppBase', 'FileChooserDialog', 'Entry', '_',
           'confirm_dialog', 'info_dialog']

try:
    import hildon
    MAEMO = True
    AppBase = hildon.Program
    Window = hildon.Window
    StackableWindow = hildon.StackableWindow
    TextView = hildon.TextView
    FileChooserDialog = hildon.FileChooserDialog
    Entry = hildon.Entry
    __all__.append('hildon')

    def Entry(size="auto", *a, **kw):
        return hildon.Entry(size, *a, **kw)

    def _message_dialog(type, parent, text="", secondary_text=""):
        if secondary_text:
            text += "\n" + secondary_text
        dlg = hildon.Note(type, parent, text)
        return dlg
except ImportError:
    MAEMO = False
    AppBase = object
    Window = gtk.Window
    StackableWindow = gtk.Window
    TextView = gtk.TextView
    Entry = gtk.Entry
    FileChooserDialog = gtk.FileChooserDialog

    def _message_dialog(type, parent, text="", secondary_text=""):
        if type == "confirmation":
            buttons = gtk.BUTTONS_OK_CANCEL
            type = gtk.MESSAGE_QUESTION
        elif type == "information":
            buttons = gtk.BUTTONS_OK
            type = gtk.MESSAGE_INFO
        else:
            raise ValueError("unknown type")
        dlg = gtk.MessageDialog(parent=parent, type=type, buttons=buttons)
        dlg.set_markup("<b>" + text + "</b>")
        dlg.format_secondary_text(secondary_text)
        return dlg

confirm_dialog = lambda *a, **kw: _message_dialog("confirmation", *a, **kw)
info_dialog = lambda *a, **kw: _message_dialog("information", *a, **kw)

__all__.extend(guithread.__all__)
