from traits.api import Str, Range, HasTraits, Instance, Dict, Float, Bool, on_trait_change, List, DelegatesTo
from traitsui.api import Item, View, HGroup, VGroup, TextEditor, InstanceEditor, ListEditor

import chaco.api as chaco
from enable.component_editor import ComponentEditor
from chaco.tools.api import PanTool, ZoomTool, LegendTool, TraitsTool, DragZoom
from pyface.api import GUI

from viewers import Viewer
from variables import Expression

import threading as t
import numpy

"""
colours_list = [
  (0xED,0xD4,0x00),
  (0xF5,0x79,0x00),
  (0xC1,0x7D,0x11),
  (0x73,0xD2,0x16),
  (0x34,0x65,0xA4),
  (0x75,0x50,0x7B),
  (0xCC,0x00,0x00),
  (0x2E,0x34,0x36),
]
"""
colours_list = ['red', 'blue', 'green']

class MyPlotData(chaco.ArrayPlotData):
  def set_data(self, name, new_data, generate_name=False, do_update=True):
      if generate_name:
          # Find all 'series*' and increment
          candidates = [n[6:] for n in self.arrays.keys() if n.startswith('series')]
          max_int = 0
          for c in candidates:
              try:
                  if int(c) > max_int:
                      max_int = int(c)
              except ValueError:
                  pass
          name = "series%d" % (max_int + 1)

      self.arrays[name] = new_data
      if do_update:
        event = {}
        if name in self.arrays:
            event['changed'] = [name]
        else:
            event['added'] = [name]
        self.data_changed = event
      return name

class Plot(Viewer):
  name = Str('Plot')

  plot = Instance(chaco.Plot)
  legend = Instance(chaco.Legend)  
  plot_data = Instance(MyPlotData, ())
  
  y_exprs = List(Instance(Expression))
  x_expr = Instance(Expression)
  
  x_label = Str
  x_max = Float
  x_max_auto = Bool(True)
  x_min = Float
  x_min_auto = Bool(True)
  
  y_label = Str
  y_max = Float
  y_max_auto = Bool(True)
  y_min = Float
  y_min_auto = Bool(True)
  
  scroll = Bool(True)
  scroll_width = Float(300)
  
  #legend = Bool(False)
  
  index_range = DelegatesTo('plot')
  value_range = DelegatesTo('plot')

  traits_view = View(
    Item(name = 'name', label = 'Plot name'),
    Item(label = 'Use commas\nfor multi-line plots.'),
    Item(name = 'legend', label = 'Show legend'),
    VGroup(
      Item(name = 'index_range', label = 'Index range', editor = InstanceEditor()),
      Item(name = 'x_expr', label = 'Expression', style = 'custom'),
      HGroup(
        Item(name = 'x_max', label = 'Max'),
        Item(name = 'x_max_auto', label = 'Auto')
      ),
      HGroup(
        Item(name = 'x_min', label = 'Min'),
        Item(name = 'x_min_auto', label = 'Auto')
      ),
      HGroup(
        Item(name = 'scroll', label = 'Scroll'),
        Item(name = 'scroll_width', label = 'Scroll width'),
      ),
      Item(name = 'x_label', label = 'Label'),
      label = 'X', show_border = True
    ),
    VGroup(
      Item(name = 'value_range', label = 'Value range', editor = InstanceEditor()),
      Item(name = 'y_exprs', label = 'Expression(s)', style = 'custom', editor=ListEditor(style = 'custom')),
      HGroup(
        Item(name = 'y_max', label = 'Max'),
        Item(name = 'y_max_auto', label = 'Auto')
      ),
      HGroup(
        Item(name = 'y_min', label = 'Min'),
        Item(name = 'y_min_auto', label = 'Auto')
      ),
      Item(name = 'y_label', label = 'Label'),
      label = 'Y', show_border = True
    ),
    title = 'Plot settings',
    resizable = True
  )
  
  view = View(
    Item(
      'plot',
      editor = ComponentEditor(bgcolor = (0.8,0.8,0.8)),
      show_label = False,
    ),
    resizable = True
    )

  @on_trait_change('name')
  def update_name(self, new_name):
    if self.plot:
      self.plot.title = new_name
      #GUI.invoke_later(self.plot.request_redraw)

  @on_trait_change('x_label')
  def update_x_label(self, new_name):
    if self.plot:
      self.plot.index_axis.title = new_name
      #GUI.invoke_later(self.plot.request_redraw)
    
  @on_trait_change('y_label')
  def update_y_label(self, new_name):
    if self.plot:
      self.plot.value_axis.title = new_name
      #GUI.invoke_later(self.plot.request_redraw)

  def start(self):
    self.plot = chaco.Plot(self.plot_data, title=self.name, auto_colors=colours_list)
    self.plot.value_range.tight_bounds = False
    self.legend = chaco.Legend(component=self.plot, padding=10, align="ul")
    self.legend.tools.append(LegendTool(self.legend, drag_button="right"))
    self.plot.overlays.append(self.legend)
    self.legend.plots = self.plot.plots
    #self.y_exprs += [self.variables.new_expression('a')]
    #self.x_expr = self.variables.new_expression('i')
    self.update_y_exprs()

  def get_config(self):
    exprs = [expr._expr for expr in self.y_exprs]
    return {
        'name': self.name,
        'x_label': self.x_label,
        'y_label': self.y_label,
        'expressions': exprs
    }

  def set_config(self, config):
    exprs = [self.variables.new_expression(expr) for expr in config['expressions']]
    self.y_exprs = exprs
    self.name = config['name']
    self.x_label = config['x_label']
    self.y_label = config['y_label']

  def add_expr(self, expr):
    self.y_exprs.append(self.variables.new_expression(expr))
    self.update_y_exprs()

  @on_trait_change('y_exprs')
  def update_y_exprs(self):
    if self.plot:
      if self.plot.plots:
        for plot in list(self.plot.plots.iterkeys()):
          self.plot.delplot(plot)
      for n, expr in enumerate(self.y_exprs):
        if expr is None:
          # Initialise a new expression if we added one
          self.y_exprs[n] = self.variables.new_expression('0.5')
        ys = self.y_exprs[n].get_array()
        self.plot_data.set_data(str(n), ys)
        self.plot_data.set_data('x', range(len(ys)))
        self.plot.plot(('x', str(n)), name = self.y_exprs[n]._expr, style='line', color='auto')
      #self.update()
      self.legend.plots = self.plot.plots

  @on_trait_change('x_expr')
  def update_x_expr(self):
    self.update()

  def get_x_bounds(self, x_low, x_high, margin, tight_bounds):
    if self.scroll:
      x_max = max(xs)
      x_min = x_max = self.scroll_width
      if x_min < 0:
        x_min = 0
    else:
      x_max = self.x_max
      x_min = self.x_min
      if self.x_max_auto:
        x_max = max(xs)
      if self.x_min_auto:
        x_min = min(xs)
    return (x_min, x_max)

  def get_y_bounds(self, y_low, y_high, margin, tight_bounds):
    y_max = self.y_max
    y_min = self.y_min
    if self.y_max_auto:
      y_max = max(ys)
    if self.y_min_auto:
      y_min = min(ys)
    return (y_min, y_max)

  def update(self):
    from pyface.api import GUI
    GUI.invoke_later(self.update_unsafe)

  def update_unsafe(self):
    if self.plot:
      last = self.variables.sample_number
      yss = [y_expr.get_array(last = last) for y_expr in self.y_exprs]
      self.plot_data.set_data('x', numpy.arange(len(yss[0])))
      for n, ys in enumerate(yss):
        self.plot_data.set_data(str(n), ys)


