#!/usr/bin/env python

try:
  import psyco
  psyco.full()
except:
  print "Psyco JIT compiler not found; skipping."  

# If wxversion is installed, make sure we are
# using wx >= 2.8
try:
  import wxversion
  wxversion.select('2.8')
except ImportError:
  pass

from io_driver import IODriver, IODriverList
from data_decoder import DataDecoder
from viewers import Viewer, Viewers
from variables import Variables

from plugins.io_drivers_all import *
from plugins.decoders_all import *
from plugins.viewers_all import *

from plugin_manager import *

from enthought.traits.api import HasTraits, Str, Regex, List, Instance, DelegatesTo
from enthought.traits.ui.api import TreeEditor, TreeNode, View, Item, VSplit, \
  HGroup, Controller, Handler, Group, Include, ValueEditor, HSplit, ListEditor, InstanceEditor
from enthought.traits.ui.menu import Menu, Action, Separator, MenuBar

import yaml
import wx

PROFILE = False
PROFILE_BUILTINS = True
if PROFILE:
  import yappi
  yappi.start(PROFILE_BUILTINS)

def open_file(wildcard = '', dir = './saved_sessions', file_name = '', message = 'Open'):
  dialog = wx.FileDialog(
    None,
    wildcard = wildcard,
    defaultFile = file_name,
    defaultDir = dir,
    message = message,
    style = wx.OPEN|wx.FILE_MUST_EXIST
  )
  file_name = ''
  if dialog.ShowModal() == wx.ID_OK:
    file_name = dialog.GetPath()
  dialog.Destroy()
  return file_name

def save_file(wildcard = '', dir = './saved_sessions', file_name = '', message = 'Save'):
  dialog = wx.FileDialog(
    None,
    wildcard = wildcard,
    defaultFile = file_name,
    defaultDir = dir,
    message = message,
    style = wx.SAVE|wx.OVERWRITE_PROMPT
  )
  filename = ''
  
  # take odd elements of the wildcard list and take the last part after the dot
  extensions = [wc.split('.')[-1] for wc in wildcard.split('|')[1::2]]
  # get rid of any '*'s i.e. no extension
  extensions = ['' if e == '*' else e for e in extensions]
  
  if dialog.ShowModal() == wx.ID_OK:
    extension = extensions[dialog.GetFilterIndex()]
    filename = dialog.GetPath()
    if filename.split('.')[-1] != extension and extension:
      filename += '.' + extension
  dialog.Destroy()
  return filename

class PlotOMaticHandler(Controller):
  # ------------ Menu related --------------------
  exit_action = Action(name='&Exit', action='exit')
  save_session_action = Action(name='&Open Session', action='open_session', accelerator='Ctrl+O')
  open_session_action = Action(name='&Save Session', action='save_session', accelerator='Ctrl+S')

  file_menu = Menu(
      exit_action,
      Separator(),
      save_session_action,
      open_session_action,
      name = '&File'
  )

  def exit(self, uii):
    print 'Exit called, really should implement this'

  def save_session(self, uii):
    filename = save_file(
      wildcard = 'Plot-o-matic session (*.plot_session)|*.plot_session|All files (*)|*', 
      file_name = 'my_session.plot_session',
      message = 'Save session'
    )
    if filename != '':
      print "Saving session as '%s'" % filename
      session = uii.object.get_config()
      fp = open(filename, 'w')
      yaml.safe_dump(session, fp, default_flow_style=False)
      fp.close()

  def open_session(self, uii):
    filename = open_file(
      wildcard = 'Plot-o-matic session (*.plot_session)|*.plot_session|All files (*)|*',
      file_name = 'my_session.plot_session',
      message = 'Open session'
    )
    if filename != '':
      print "Opening session '%s'" % filename
      fp = open(filename, 'r')
      session = yaml.load(fp)
      fp.close()
      uii.object.set_config(session)
  
  clear_data_action = Action(name = '&Clear Data', action='clear_data', accelerator='Ctrl+W')
  save_data_action = Action(name = '&Save Data Set', action='save_data', accelerator='Ctrl+Shift+S')
  open_data_action = Action(name = '&Open Data Set', action='open_data', accelerator='Ctrl+Shift+O')

  data_menu = Menu(
      clear_data_action,
      Separator(),
      save_data_action,
      open_data_action,
      name = '&Data'
  )

  def clear_data(self, uii):
    uii.object.variables.clear()

  def save_data(self, uii):
    filename = save_file(
      wildcard = 'Plot-o-matic data set (*.plot_data)|*.plot_data|All files (*)|*',
      file_name = 'my_data.plot_data',
      message = 'Save data set'
    )
    if filename != '':
      uii.object.variables.save_data_set(filename)
      print "Saved data set '%s'" % filename

  def open_data(self, uii):
    filename = open_file(
      wildcard = 'Plot-o-matic data set (*.plot_data)|*.plot_data|All files (*)|*',
      file_name = 'my_data.plot_data',
      message = 'Open data set'
    )
    if filename != '':
      uii.object.variables.open_data_set(filename)
      print "Opened data set '%s'" % filename


  # ------------ Tree related --------------------

  remove_io_driver_action = Action(name='Remove', action='handler.remove_io_driver(editor,object)')
  add_io_driver_actions_menu = Instance(Menu)

  remove_decoder_action = Action(name='Remove', action='handler.remove_decoder(editor,object)')
  add_decoder_actions_menu = Instance(Menu)

  remove_viewer_action = Action(name='Remove', action='handler.remove_viewer(editor,object)')
  open_viewer_in_window_action = Action(name='Open in new window', action='handler.open_viewer_in_window(editor,object)')
  add_viewer_actions_menu = Instance(Menu)

  refresh_tree_action = Action(name='Refresh', action='handler.refresh_tree(editor)')

  def refresh_tree(self, editor):
    editor.update_editor()

  def _add_io_driver_actions_menu_default(self):
    actions = []
    for io_driver_plugin in find_io_driver_plugins():
      actions += [Action(
        name = io_driver_plugin.__name__,
        action = 'handler.add_io_driver(editor,object,"%s")' % io_driver_plugin.__name__
      )]
    return Menu(name = 'Add', *actions)

  def remove_io_driver(self, editor, io_driver_object):
    io_driver_list = editor._menu_parent_object
    io_driver_list._remove_io_driver(io_driver_object)
    editor.update_editor()

  def add_io_driver(self, editor, io_driver_list, new_io_driver_name):
    new_io_driver = get_io_driver_plugin_by_name(new_io_driver_name)()
    io_driver_list._add_io_driver(new_io_driver)
    editor.update_editor()

  def _add_decoder_actions_menu_default(self):
    actions = []
    for decoder_plugin in find_decoder_plugins():
      actions += [Action(
        name = decoder_plugin.__name__,
        action = 'handler.add_decoder(editor,object,"%s")' % decoder_plugin.__name__
      )]
    return Menu(name = 'Add', *actions)

  def remove_decoder(self, editor, decoder_object):
    parent_io_driver = editor._menu_parent_object
    parent_io_driver._remove_decoder(decoder_object)
    editor.update_editor()

  def add_decoder(self, editor, io_driver, decoder_name):
    io_driver_list = editor._menu_parent_object
    new_decoder = get_decoder_plugin_by_name(decoder_name)()
    io_driver._add_decoder(new_decoder)
    editor.update_editor()
    
  def _add_viewer_actions_menu_default(self):
    actions = []
    for viewer_plugin in find_viewer_plugins():
      actions += [Action(
        name = viewer_plugin.__name__,
        action = 'handler.add_viewer(editor,object,"%s")' % viewer_plugin.__name__
      )]
    return Menu(name = 'Add', *actions)

  def remove_viewer(self, editor, viewer_object):
    viewers = editor._menu_parent_object.viewers_instance
    viewers._remove_viewer(viewer_object)
    editor.update_editor()

  def add_viewer(self, editor, object, viewer_name):
    new_viewer = get_viewer_plugin_by_name(viewer_name)()
    object.viewers_instance._add_viewer(new_viewer)
    editor.update_editor()

  def open_viewer_in_window(self, editor, viewer):
    viewers = editor._menu_parent_object.viewers_instance
    viewers.open_viewer_in_window(viewer)

class PlotOMatic(HasTraits):
  io_driver_list = Instance(IODriverList)
  variables = Instance(Variables)
  viewers = Instance(Viewers)
  selected_viewer = Instance(Viewer)
  
  handler = PlotOMaticHandler()

  viewer_node = TreeNode( 
    node_for  = [Viewer],
    auto_open = True,
    label     = 'name',
    menu      = Menu(
      handler.open_viewer_in_window_action,
      handler.remove_viewer_action,
      handler.refresh_tree_action
    ),
    icon_path = 'icons/',
    icon_item = 'plot.png'
  )

  tree_editor = TreeEditor(
    nodes = [
      TreeNode( 
        node_for  = [IODriverList],
        auto_open = True,
        children  = 'io_drivers',
        label     = '=Input Drivers',
        menu      = Menu(
          handler.add_io_driver_actions_menu,
          handler.refresh_tree_action
        ),
        view      = View(),
      ),
      TreeNode( 
        node_for  = [IODriver],
        auto_open = True,
        children  = '_decoders',
        label     = 'name',
        add       = [DataDecoder],
        menu      = Menu(
          handler.remove_io_driver_action,
          handler.add_decoder_actions_menu,
          handler.refresh_tree_action
        ),
        icon_path = 'icons/',
        icon_open = 'input.png',
        icon_group = 'input.png'
      ),
      TreeNode( 
        node_for  = [DataDecoder],
        auto_open = True,
        children  = '',
        label     = 'name',
        menu      = Menu(
          handler.remove_decoder_action,
          handler.refresh_tree_action
        ),
        icon_path = 'icons/',
        icon_item = 'decoder.png'
      ),
      TreeNode( 
        node_for  = [IODriverList],
        auto_open = True,
        children  = 'viewers',
        label     = '=Viewers',
        menu      = Menu(
          handler.add_viewer_actions_menu,
          handler.refresh_tree_action
        ),
        view      = View()
      ),
      viewer_node
    ],
    hide_root = True,
    orientation = 'vertical'
  )

  view = View(
    HSplit(
      Item(
        name = 'io_driver_list',
        editor = tree_editor,
        resizable = True,
        show_label = False,
        width = .32
      ),
      VSplit(
        Item(
          name = 'selected_viewer',
          style = 'custom',
          resizable = True,
          show_label = False,
          editor = InstanceEditor(
            view = 'view'
          )
        ),
        Item(
          name = 'variables', 
          show_label = False,
          style = 'custom',
          height = .3
        )
      )
    ),
    menubar = MenuBar(
      handler.file_menu,
      handler.data_menu
    ),
    title = 'Plot-o-matic',
    resizable = True,
    width = 1000,
    height = 600,
    handler = PlotOMaticHandler()
  )
  
  def __init__(self, **kwargs):
    HasTraits.__init__(self, **kwargs)
    self.viewer_node.on_select = self.click_viewer
    
  def click_viewer(self, viewer):
    self.selected_viewer = self.viewers.select_viewer(viewer)

  def start(self):
    self.io_driver_list.start_all()
    self.viewers.start()

  def stop(self):
    self.viewers.stop()
    self.io_driver_list.stop_all()

  def get_config(self):
    config = {}
    config['io_drivers'] = self.io_driver_list.get_config()
    config['viewers'] = self.viewers.get_config()
    return config

  def set_config(self, config):
    if 'io_drivers' in config:
      self.io_driver_list.set_config(config['io_drivers'])
    if 'viewers' in config:
      self.viewers.set_config(config['viewers'])
    self.variables.clear()

vs = Variables()
viewers = Viewers(variables = vs)


iodl = IODriverList(variables = vs, viewers_instance = viewers)
proj = PlotOMatic(io_driver_list = iodl, variables = vs, viewers = viewers)

proj.start()
proj.configure_traits()
proj.stop()

if PROFILE:
  print "Generating Statistics"
  yappi.stop()
  stats = yappi.get_stats(yappi.SORTTYPE_TSUB, yappi.SORTORDER_DESCENDING, 300) #yappi.SHOW_ALL)
  for stat in stats: 
      print stat
