from traits.api import Str
from traitsui.api import View

import sys

from io_driver import IODriver

class StdinDriver(IODriver):
  """
      Simple driver for taking input from stdin.
  """

  name = Str('Stdin Driver')
  view = View(
    title='Stdin input driver'
  )
  
  def receive(self):    
    return sys.stdin.readline() 
