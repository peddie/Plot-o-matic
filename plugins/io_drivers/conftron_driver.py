from traits.api import Str, Float, Range, Int, Bool, on_trait_change
from traitsui.api import View, Item
import sys
from os import environ
from collections import deque

from io_driver import IODriver

class ConftronDriver(IODriver):
  """
      Conftron input driver.
  """
  _use_thread = True

  name = Str('Conftron Driver')
  view = View(
    Item(name='show_debug_msgs', label='Show debug messages'),
    title='Conftron input driver'
  )
  
  show_debug_msgs = Bool(True)

  def subscribe_to_msg(self, msg, tcmod):
    # This relies on the configuration library to make a handler that
    # turns lcm structs into plot-o-matic dicts.  
    hdl = self.conf.make_lcm_handler_from_telem(msg)
    msgtype = getattr(tcmod, msg.type)
    def msghdl(channel, data):
      self.queued_messages.append(hdl(msgtype.decode(data)))
    self.subs.append(self.lc.subscribe(msg.channel % msg, msghdl))
    
  def open(self):
    self.queued_messages = deque([]) #fifo buffer

    # set up paths
    self.ap_project_root = environ.get('AP_PROJECT_ROOT')
    if self.ap_project_root == None:
      raise NameError("please set the AP_PROJECT_ROOT environment variable to use Conftron driver")
    sys.path.append( self.ap_project_root+"/conftron/python/" )
    sys.path.append( self.ap_project_root+"/conftron/" )
    import configuration

    # create lcm instance
    import lcm
    self.lc = lcm.LCM()

    self.conf = configuration.Configuration()
    self.subs = []
    for tc in self.conf.telemetry:
      tcmod = __import__(tc.classname)
      for msg in tc.messages:
        if not msg.has_key('plotomatic'):
          self.subscribe_to_msg(msg, tcmod)
        if msg.has_key('plotomatic') and msg.plotomatic != 'ignore':
          self.subscribe_to_msg(msg, tcmod)

  def close(self):
    for s in self.subs:
      self.lc.unsubscribe(s)

  def pop_queue(self):
    # empty self.queued_messages
    if len(self.queued_messages) > 0:
      if len(self.queued_messages) > 10:
        print "Conftron message queue length: "+str(len(self.queued_messages))
      return self.queued_messages.popleft()
    return None

  def receive(self):
    ret = self.pop_queue()
    if ret != None:
      return ret

    self.lc.handle()

    ret = self.pop_queue()
    if ret != None:
      return ret

  def get_config(self):
    return {'hi':'there'}

  def set_config(self, config):
    return None



#  @on_trait_change('show_debug_messages')
#  def change_port(self):
#    self.rebind_socket()
    

if __name__ == '__main__':
  cd = ConftronDriver()
  cd.open()
  try:
    while True:
        cd.lc.handle()
  except KeyboardInterrupt:
    pass

  for msg in cd.messages.values():
    cd.lc.unsubscribe(msg['subscription'])
