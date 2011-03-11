from enthought.traits.api import Str, Bool, Enum, List
from enthought.traits.ui.api import View, Item
from data_decoder import DataDecoder

class ConftronDecoder(DataDecoder):
#class ConftronDecoder():
  """
      Conftron lcm class decoder
  """
  name = Str('Conftron Decoder')
  
  view = View(
    title='Conftron Decoder'
  )
  
  _names = List()
  def __init__(self):
    pass

  def decode(self, message):
    """
        Decodes input from Conftron/LCM messages.
    """
    return message

  def get_config(self):
    return {'hi':'there'}

  def set_config(self, config):
    return None

if __name__ == '__main__':
  cd = ConftronDecoder()
