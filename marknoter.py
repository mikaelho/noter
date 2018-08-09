#coding: utf-8
from ui import *
from objc_util import *

from extend import Extender
from scripter import *
from gestures import *
from ReminderStore import ReminderStore
import checkbox
import evernoteparser

eparser = evernoteparser.EvernoteParser()

import random

from noterconf import *

global_width_unit = int(min(get_screen_size())/2.2)

class LocalModel():
  
  def __init__(self):
    self.local_storage = ReminderStore(
        namespace=reminder_namespace, to_json=True, cache=False)
    self.local_management = ReminderStore(
        namespace=management_namespace, to_json=True, cache=False)

    if 'dirty' in self.local_storage:
      self.local_management['dirty'] = self.local_storage['dirty']
      del self.local_storage['dirty']
    if 'order' in self.local_storage:
      self.local_management['order'] = self.local_storage['order']
      del self.local_storage['order']
    
    #TODO: activate loading from evernote
    #if 'dirty' not in self.local_management:
    #  load_all_from_evernote()
    if 'order' not in self.local_management:
      self.local_management['order'] = [ id for id in self.local_storage ]
      
  def get_notes_list(self):
    order_list = self.local_management['order']
    for id in self.local_storage:
      if id not in order_list:
        order_list.append(id)
    self.local_management['order'] = order_list
    
    note_list = []

    removed = []
    section_on = True
    for id in self.local_management['order']:
      note = self.local_storage[id]
      if not note:
        removed.append(id)
        continue
      else:
        note_list.append(note)
      #TODO: sections, groups...
      #if note['section']:
      #  section_on = section_on == False
  
      #TODO: checkboxes
      #checkbox_true = '<input type="checkbox" checked="true"/>'
      #checkbox_false = '<input type="checkbox"/>'
      
    cleaned_list = [id for id in self.local_management['order'] if id not in removed]
    self.local_management['order'] = cleaned_list
    
    return note_list
    

class DeskView(View):
  
  def __init__(self, model, scroll_view, **kwargs):
    super().__init__(**kwargs)
    self.model = model
    self.scroll_view = scroll_view
    scroll_view.directional_lock_enabled = True
    self.scale = 1
    g = Gestures()
    g.add_pinch(self, self.pinch_handler)
  
  @on_main_thread
  def lay_cards_out(self):
    notes = self.model.get_notes_list()
    self.cards = [ CardView(note['title'], note['content']) for note in notes]
    for card in self.cards:
      self.add_subview(card)
    
    total_height = 5
    gap = 5
    card_width = global_width_unit
    for card in self.cards:
      card.size_to_fit()
      total_height += card.height + gap
    
    current_x = current_y = gap
    max_height = 0
    for card in self.cards:
      card.x = current_x
      card.y = current_y
      current_y += card.height + gap
      max_height = max(max_height, current_y)
      if current_y > get_screen_size()[1]*1.3:
        current_x += card_width + gap
        current_y = gap
    
    self.width = current_x + card_width + gap
    self.height = max_height
    self.scroll_view.content_size = (self.width, self.height)
    
  def pinch_handler(self, data):
    if data.state == Gestures.BEGAN:
      self.prev_location = Vector(convert_point(data.location, self))
    if data.state == Gestures.CHANGED:
      pre_screen = Vector(convert_point(data.location, self))
      move_delta = pre_screen - self.prev_location
      self.prev_location = pre_screen
      scale_now = self.scale * data.scale
      if self.width * scale_now < self.scroll_view.width or self.height *scale_now < self.scroll_view.height:
        return
      self.transform = Transform.scale(scale_now, scale_now)
      #self.x, self.y = 0, 0
      self.scroll_view.content_size = self.width * scale_now, self.height * scale_now
      post_screen = Vector(convert_point(data.location, self))
      self.scroll_view.content_offset += tuple(post_screen-pre_screen-move_delta)
      delta = (self.x, self.y)
      self.x, self.y = 0, 0
      self.scroll_view.content_offset -= delta
      offset = self.scroll_view.content_offset
      offx, offy = offset
      fixx, fixy = 0, 0
      if offx < 0:
        fixx = -offx
      if offy < 0:
        fixy = -offy
      deltax = offx + self.scroll_view.width - self.width
      deltay = offy + self.scroll_view.height - self.height
      if deltax < 0:
        pass#fixx = deltax
      if deltay < 0:
        pass#fixy = deltay
      self.scroll_view.content_offset += (fixx, fixy)
    elif data.state == Gestures.ENDED:
      self.scale = self.scale * data.scale
      
      
class CardStack(View):
  
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.tf = tf = TextField(frame=self.bounds, flex='WH')
    self.add_subview(tf)
    
  def size_to_fit(self):
    self.tf.size_to_fit()
    self.height = self.tf.height
    
class CardView(View):

  def __init__(self, title, contents, **kwargs):
    super().__init__(**kwargs)
    self.background_color = 'white'
    contents = self.evernote_to_local(contents)
    
    self.tf = tf = Markdown(TextView(text=title, frame=(0,0,self.width,30), flex='W', font=('Arial Rounded MT Bold',12), background_color='white', scroll_enabled=False))
    #tf.objc_instance.subviews()[0].setBorderStyle(0)
    self.tv = tv = Markdown(TextView(frame=(0,tf.height,self.width,self.height-tf.height), flex='WH', scroll_enabled=False, font=('Apple SD Gothic Neo', 8)))
    objc_font = ObjCClass('UIFont').fontWithName_size_('Apple SD Gothic Neo', 8.)
    paragraph_style = ObjCClass('NSMutableParagraphStyle').alloc().init()
    paragraph_style.paragraphSpacing = 0.75 * objc_font.lineHeight()
    attributes = {'NSParagraphStyle': paragraph_style}
    attribute_string = ObjCClass('NSMutableAttributedString').alloc()
    attribute_string.initWithString_attributes_(contents, attributes)
    tv.objc_instance.attributedText = attribute_string 
    self.add_subview(tf)
    self.add_subview(tv)
    
    g = Gestures()
    #g.add_pan(tv, self.long_press_handler, minimum_number_of_touches = 2, maximum_number_of_touches = 2)
    g.add_force_press(tv, self.long_press_handler)
    
  def evernote_to_local(self, contents):  
    contents = eparser.feed(contents).strip()
    return contents
    
  def size_to_fit(self):
    self.tv.width = global_width_unit
    self.tv.size_to_fit()
    self.height = self.tf.height + self.tv.height
    self.width = self.tf.width = self.tv.width = global_width_unit
    
  def long_press_handler(self, data):
    if data.state == Gestures.BEGAN:
      self.prev_pos = convert_point(data.location, self)
    if data.state == Gestures.CHANGED:
      current_pos = convert_point(data.location, self)
      delta = current_pos - self.prev_pos
      self.prev_pos = current_pos
      self.x += delta.x
      self.y += delta.y


class Markdown(Extender):

  def __init__(self):
    self.create_accessory_toolbar()
    self.delegate = self
    self.to_add_to_beginning = ('', -1)
    self.set_keyboard_dismiss_mode()
    self.caret_pos = self.objc_instance.selectedTextRange().start()

  # Temporary fix for a bug where setting selected_range throws a range error if placing caret at the end of the text
  @on_main_thread
  def set_selected_range(self, start, end):
    ObjCInstance(self).setSelectedRange_((start, (end-start)))

  @on_main_thread
  def set_keyboard_dismiss_mode(self):
    ObjCInstance(self).keyboardDismissMode = 2
    # 0 - normal
    # 1 - on scroll
    # 2 - on scroll interactive

  @on_main_thread
  def create_accessory_toolbar(self):

    def create_button(label, func):
      button_width = 25
      black = ObjCClass('UIColor').alloc().initWithWhite_alpha_(0.0, 1.0)
      action_button = Button()
      action_button.action = func
      accessory_button = ObjCClass('UIBarButtonItem').alloc().initWithTitle_style_target_action_(label, 0, action_button, sel('invokeAction:'))
      accessory_button.width = button_width
      accessory_button.tintColor = black

      return (action_button, accessory_button)

    vobj = ObjCInstance(self)

    keyboardToolbar = ObjCClass('UIToolbar').alloc().init()

    keyboardToolbar.sizeToFit()

    Gestures().add_swipe(keyboardToolbar, self.hide_keyboard, Gestures.DOWN)

    Gestures().add_pan(keyboardToolbar, self.move_caret)

    button_width = 25
    black = ObjCClass('UIColor').alloc().initWithWhite_alpha_(0.0, 1.0)

    # Create the buttons
    # Need to retain references to the buttons used
    # to handle clicks
    (self.indentButton, indentBarButton) = create_button(u'\u21E5', self.indent)

    (self.outdentButton, outdentBarButton) = create_button(u'\u21E4', self.outdent)

    (self.quoteButton, quoteBarButton) = create_button('>', self.block_quote)

    (self.linkButton, linkBarButton) = create_button('[]', self.link)

    #(self.anchorButton, anchorBarButton) = create_button('<>', self.anchor)

    (self.hashButton, hashBarButton) = create_button('#', self.heading)

    (self.numberedButton, numberedBarButton) = create_button('1.', self.numbered_list)

    (self.listButton, listBarButton) = create_button('*', self.unordered_list)

    (self.underscoreButton, underscoreBarButton) = create_button('_', self.insert_underscore)

    (self.backtickButton, backtickBarButton) = create_button('`', self.insert_backtick)

    (self.newButton, newBarButton) = create_button('+', self.new_item)

    (self.checkboxButton, checkboxBarButton) = create_button('\u2610', self.add_checkbox)

    # Flex between buttons
    f = ObjCClass('UIBarButtonItem').alloc().initWithBarButtonSystemItem_target_action_(5, None, None)

    doneBarButton = ObjCClass('UIBarButtonItem').alloc().initWithBarButtonSystemItem_target_action_(0, vobj, sel('endEditing:'))

    keyboardToolbar.items = [f, listBarButton, f, numberedBarButton, f, indentBarButton, f, outdentBarButton, f, checkboxBarButton, f, doneBarButton]
    vobj.inputAccessoryView = keyboardToolbar

  def indent(self, sender):
    def func(line):
      return '  ' + line
    self.transform_lines(func)

  def outdent(self, sender):
    def func(line):
      if str(line).startswith('  '):
        return line[2:]
    self.transform_lines(func, ignore_spaces = False)

  def insert_underscore(self, sender):
    self.insert_character('_', '___')

  def insert_backtick(self, sender):
    self.insert_character('`', '`')

  def insert_character(self, to_insert, to_remove):
    tv = self
    (start, end) = tv.selected_range
    (r_start, r_end) = (start, end)
    r_len = len(to_remove)
    if start != end:
      if tv.text[start:end].startswith(to_remove):
        if end - start > 2*r_len + 1 and tv.text[start:end].endswith(to_remove):
          to_insert = tv.text[start+r_len:end-r_len]
          r_end = end-2*r_len
      elif start-r_len > 0 and tv.text[start-r_len:end].startswith(to_remove):
        if end+r_len <= len(tv.text) and tv.text[start:end+r_len].endswith(to_remove):
          to_insert = tv.text[start:end]
          start -= r_len
          end += r_len
          r_start = start
          r_end = end-2*r_len
      else:
        r_end = end + 2*len(to_insert)
        to_insert = to_insert + tv.text[start:end] + to_insert
    tv.replace_range((start, end), to_insert)
    if start != end:
      tv.set_selected_range(r_start, r_end)

  def heading(self, sender):
    def func(line):
      return line[3:] if str(line).startswith('###') else '#' + line
    self.transform_lines(func, ignore_spaces = False)

  def numbered_list(self, data):
    def func(line):
      if line.startswith('1. '):
        return line[3:]
      else:
        return '1. ' + (line[2:] if line.startswith('• ') else line)
    self.transform_lines(func)

  def unordered_list(self, sender):
    def func(line):
      if str(line).startswith('• '):
        return line[2:]
      else:
        return '• ' + (line[3:] if line.startswith('1. ') else line)
    self.transform_lines(func)

  def block_quote(self, sender):
    def func(line):
      return '> ' + line
    self.transform_lines(func, ignore_spaces = False)

  def link(self, sender):
    templ = "[#]($)"
    (start, end) = self.selected_range
    templ = templ.replace('$', self.text[start:end])
    new_start = start + templ.find('#')
    new_end = new_start + (end - start)
    templ = templ.replace('#', self.text[start:end])
    self.replace_range((start, end), templ)
    self.set_selected_range(new_start, new_end)

  def new_item(self, sender):
    (start, end) = self.selected_range
    (new_key, value) = self.new_item_func(self.text[start:end])
    link = '[' + value + '](awz-' + new_key + ')'
    self.replace_range((start, end), link)
    
  def add_checkbox(self, sender):
    (start, end) = self.selected_range
    self.replace_range((start, end), '[o]')

  def hide_keyboard(self, data):
    self.end_editing()

  def move_caret(self, data):
    if data.velocity[1] > 500 and data.translation[1] > 50:
      self.end_editing()
      return
    if data.state == Gestures.BEGAN:
      self.translation_baseline = 0
    dx = data.translation[0] - self.translation_baseline
    if abs(dx) > 15:
      self.translation_baseline = data.translation[0]
      change = 1 if dx > 0 else -1
      (start, end) = self.selected_range
      new_start = start + change
      (ns, ne) = (start, new_start) if dx > 0 else (new_start, start)
      if ns > -1:
        if not self.text[ns:ne] == '\n':
          self.set_selected_range(new_start, new_start)

  def transform_lines(self, func, ignore_spaces = True):
    (orig_start, orig_end) = self.selected_range
    (lines, start, end) = self.get_lines()
    replacement = []
    for line in lines:
      spaces = ''
      if ignore_spaces:
        space_count = len(line) - len(line.lstrip(' '))
        if space_count > 0:
          spaces = line[:space_count]
          line = line[space_count:]
      replacement.append(spaces + func(line))
    self.replace_range((start, end), '\n'.join(replacement))
    new_start = orig_start + len(replacement[0]) - len(lines[0])
    if new_start < start:
      new_start = start
    end_displacement = 0
    for index, line in enumerate(lines):
      end_displacement += len(replacement[index]) - len(line)
    new_end = orig_end + end_displacement
    if new_end < new_start:
      new_end = new_start
    self.set_selected_range(new_start, new_end)

  def get_lines(self):
    (start, end) = self.selected_range
    text = self.text
    new_start = text.rfind('\n', 0, start)
    new_start = 0 if new_start == -1 else new_start + 1
    new_end = text.find('\n', end)
    if new_end == -1: new_end = len(text)
    #else: new_end -= 1
    if new_end < new_start: new_end = new_start
    return (text[new_start:new_end].split('\n'), new_start, new_end)
    
  def make_checkboxes(self):
    for selected in [True, False]:
      txt = self.text
      search_index = 0
      text_to_find = '[x]' if selected else '[o]'
      
      while txt.find(text_to_find, search_index) != -1:
        found = txt.find(text_to_find, search_index)
        self.caret_pos.setOffset_(found)
        search_index = found + 1
        #(w,h) = measure_string(txt[:found], max_width=v.width, font=f)
      
        c = checkbox.Checkbox(value=selected, font=(self.font[0],self.font[1]-1))
        c.pos = found
        #c.textview = textview
        c.action = self.changed
        self.add_subview(c)
        c.width = c.height = max(measure_string('[x]', font=self.font))
        
        rect = self.objc_instance.caretRectForPosition_(self.caret_pos)
        c.x, c.y = rect.origin.x+1, rect.origin.y+1

  def changed(self, checkbox):
    #was = self.selected_range
    self.replace_range((checkbox.pos, checkbox.pos+3), '[x]' if checkbox.value else '[o]')
    #self.selected_range = was
    self.end_editing()

  def textview_did_end_editing(self, textview):
    #TODO: Update after edit
    pass
    #(start, end) = self.selected_range
    #self.changed_func(self.text)
    #self.end_edit_func(start)

  def textview_should_change(self, textview, range, replacement):
    self.to_add_to_beginning = ('', -1)
    if replacement == '\n': #and range[0] == range[1]
      pos = range[0]
      next_line_prefix = ''
      # Get to next line
      pos = self.text.rfind('\n', 0, pos)
      if not pos == -1:
        pos = pos + 1
        rest = self.text[pos:]
        # Copy leading spaces
        space_count = len(rest) - len(rest.lstrip(' '))
        if space_count > 0:
          next_line_prefix += rest[:space_count]
          rest = rest[space_count:]
        # Check for prefixes
        prefixes = [ '1. ', '+ ', '- ', '* ', '• ']
        for prefix in prefixes:
          if rest.startswith(prefix + '\n'):
            self.replace_range((pos + space_count, pos + space_count + len(prefix)), '')
            break
          elif rest.startswith(prefix):
            next_line_prefix += prefix
            break
        if len(next_line_prefix) > 0:
          diff = range[0] - pos
          if diff < len(next_line_prefix):
            next_line_prefix = next_line_prefix[:diff]
          self.to_add_to_beginning = (next_line_prefix, range[0]+1)
    elif replacement == '': # Deleting
      start, end = range
      if start > 1 and textview.text[start:end] == ']':
        prev_chars = textview.text[start-2:start]
        if prev_chars == '[x' or prev_chars == '[o':
          textview.replace_range((start-1, start+1), '')
    return True

  def textview_did_change(self, textview):
    add = self.to_add_to_beginning
    if add[1] > -1:
      self.to_add_to_beginning = ('', -1)
      self.replace_range((add[1], add[1]), add[0])
    for view in textview.subviews:
      if type(view) == checkbox.Checkbox:
        textview.remove_subview(view)
    self.make_checkboxes()
    #self.changed_func(self.text)


class MenuPanel(View):
  
  def create_menu(self, desk):
    self.desk = desk
    self.menu_open = False
    self.menu_buttons = ['MoveButton'] #['DeleteButton','AddButton','MoveButton']
    self.create_menu_button(self.toggle_menu, position=1, name='ShowMenuButton', image_name='wrench.png')
    self.create_menu_button(self.pin_notes, position=-2, name='MoveButton', image_name='pin.png', hidden=True)
    
  @script
  def toggle_menu(self, sender):
    menu_speed = 0.5
    self.menu_open = self.menu_open == False
    menu_btn = self['ShowMenuButton']
    menu_location = menu_btn.center
    if self.menu_open:
      rotate_by(menu_btn, -90, duration=menu_speed)
      slide_color(menu_btn, 'background_color', (1,1,1,0.4), duration=menu_speed)
      for button_name in self.menu_buttons:
        btn = self[button_name]
        target_location = btn.center
        btn.center = menu_location
        show(btn, duration=menu_speed)
        roll_to(btn, target_location, duration=menu_speed)
      yield
    else:
      locations = {}
      rotate_by(menu_btn, 90, duration=menu_speed)
      slide_color(menu_btn, 'background_color', 'white', duration=menu_speed)
      for button_name in self.menu_buttons:
        btn = self[button_name]
        locations[button_name] = btn.center
        hide(btn, duration=menu_speed)
        roll_to(btn, menu_location, end_right_side_up=False, duration=menu_speed)
      yield
      for button_name in self.menu_buttons:
        btn = self[button_name]
        btn.center = locations[button_name]
    
  def pin_notes(self, sender):
    pass

  def create_menu_button(self, show_menu_func, position=2, name='MenuButton', image_name='emj:Checkmark_1', color=(1,1,1,0.8), hidden=False, tint=True, tint_color='black'):
    b = Button(name=name)
    b.image = Image(image_name)
    if not tint:
      b.image = b.image.with_rendering_mode(RENDERING_MODE_ORIGINAL)
    b.tint_color = tint_color
    b.background_color = color
    b.hidden = hidden
    d = 40
    b.width = b.height = d
    b.corner_radius = 0.5 * d
    if position > 0:
      b.x = self.width - 1.5 * d
      b.y = self.height - position * 1.5 * d
    else:
      b.x = self.width + position * 1.5 * d
      b.y = self.height - 1.5 * d
    
    b.action = show_menu_func
    self.add_subview(b)
    b.bring_to_front()

if __name__ == '__main__':
  
  model = LocalModel()
  
  backpanel = View()
  
  menupanel = MenuPanel(touch_enabled=False, frame=backpanel.bounds, flex='WH')

  
  scroller = ScrollView(background_color='grey', frame=backpanel.bounds, flex='WH')
  backpanel.add_subview(scroller)
  
  desk = DeskView(model, scroller)
  scroller.add_subview(desk) 
  desk.lay_cards_out()

  backpanel.add_subview(menupanel)

  backpanel.present()
  
  menupanel.create_menu(desk)
  
  note = model.get_notes_list()[0]
  
