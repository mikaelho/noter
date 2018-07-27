# coding: utf-8

# Import Evernote auth_token, notebook_guid and ReminderStore reminder_namespace
auth_token = None
from noterconf import *

# Using Evernote Python SDK from 
# Copy evernote and thrift from lib to site-packages
#import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.type.ttypes as Types
from evernote.edam.notestore.ttypes import NoteFilter, NotesMetadataResultSpec
from evernote.api.client import EvernoteClient

from ReminderStore import ReminderStore
from scripter import *
import evernoteproxy, asyncui, asyncio

import ui, console, webbrowser

import json, re, os, math, urllib, threading
from string import Template

from objc_util import ObjCInstance, ObjCClass, on_main_thread

UIWebView = ObjCClass('UIWebView')

def _find_real_webview(view_objc):
  # Traverse subviews and find one which is UIWebView (ObjC)
  for subview_objc in view_objc.subviews():
      if subview_objc.isKindOfClass_(UIWebView.ptr):
          return subview_objc
      else:
          return _find_real_webview(subview_objc)
  return None

@on_main_thread
def _make_webview_transparent(webview):
  # See https://forum.omz-software.com/topic/4331/webview-with-transparent-background/3
  pythonista_wrapper_objc = ObjCInstance(webview)
  real_webview_objc = _find_real_webview(pythonista_wrapper_objc)
  if real_webview_objc:
      # UIWebView found

      # Make it transparent
      # https://developer.apple.com/documentation/uikit/uiview/1622622-opaque?language=objc
      real_webview_objc.setOpaque_(False)

      # Set background color to clear color
      # https://developer.apple.com/documentation/uikit/uicolor/1621945-clearcolor?language=objc
      # clear_color = ObjCClass('UIColor').clearColor()
        
spin = ui.ActivityIndicator()

note_syntax = ('<?xml version="1.0" encoding="UTF-8" standalone="no"?>', '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">', '<en-note>', '</en-note>', '<?xml version="1.0" encoding="UTF-8"?>')

todo_true = '<en-todo checked="true"/>'
todo_false = '<en-todo checked="false"/>'

nice_green = (.52, .77, .33)
nice_red = (.77, .38, .38)

if auth_token:
  client = EvernoteClient(token=auth_token, sandbox=False)
  note_store = client.get_note_store()
  user = client.get_user_store().getUser(auth_token)
  
  userId = user.id
  shardId = user.shardId

# List all of the notebooks in the user's account
#notebooks = note_store.listNotebooks()
#print("Found ", len(notebooks), " notebooks:")
#for notebook in notebooks:
#  print("  * ", notebook.name, notebook.guid)

def load_from_evernote(all_notes):
  rexp = r'(<[^>]+) style=".*?"'
  pr = re.compile(rexp, re.IGNORECASE)
  local_management['dirty'] = {}
  local_keys = dict.fromkeys(local_storage, True)
  #v['MenuButton'].background_color = 'green'
  filter = NoteFilter(notebookGuid=notebook_guid, order=Types.NoteSortOrder.TITLE)
  #if not all_notes and update_count in local_management:
    #filter.words = 
  notes = note_store.findNotesMetadata(filter, 0, 1000, NotesMetadataResultSpec())
  #notes.updateCount
  for note_data in notes.notes:
    if note_data.guid in local_keys:
      del local_keys[note_data.guid]
    note = note_store.getNote(note_data.guid, True, False, False, False)
    stripped_content = note.content
    if '<en-note/>' in stripped_content:
      stripped_content = ''
    else:
      remove_success_count = 0
      for to_remove in note_syntax:
        old_content = stripped_content
        stripped_content = old_content.replace(to_remove, '')
        if old_content != stripped_content:
          remove_success_count += 1
      if remove_success_count != 4:
        print(note.content)
        raise ValueError(f"Note content from server with title '{note.title}' did not include all mandatory parts")
      stripped_content = pr.sub(r'\1', stripped_content)
    #note_link = f'evernote:///view/{userId}/{shardId}/{note_data.guid}/{note_data.guid}/'
    to_local_store(note_data.guid, note.title, stripped_content, note.tagGuids is not None)
  for  id in local_keys:
    del local_storage[id]
  console.hud_alert('Updated from server')
    
def to_local_store(id, title, content, section):
  local_storage[id] = {
    'title': title,
    'content': content,
    'section': section
  }

main_template = Template('''
<html>
<head>
  <meta name="viewport" content="height=device-height, initial-scale=0.5">
  <meta name="format-detection" content="telephone=no">
  <script type="text/javascript">
  
    console = new Object();
    console.log = function(log) {
      window.location.href="ios-log:"+log;
      return false;
    };
    window.onerror = (function(error, url, line,col,errorobj) {
      console.log("error: "+error+"%0Aurl:"+url+" line:"+line+"col:"+col+"stack:"+errorobj);
    });
  
    function initialize() {
      //console.log("logging activated");
    }
  
    function make_editable(editable) {
      class_editable("card_title", editable);
      class_editable("card_content", editable);
      var clickable = (editable == false);
      div_clickable(clickable);
    }
    
    function class_editable(classname, editable) {
      elems = document.getElementsByClassName(classname);
      for(var i = 0; i < elems.length; i++) {
        if (editable) {
          elems[i].classList.remove("touch-transparent");
        } else {
          elems[i].classList.add("touch-transparent");
        }
      }
    }
    
    function highlight_elem(elem_id, turn_on) {
      elem = document.getElementById(elem_id);
      if (turn_on) {
        elem.classList.add("selected_card");
      } else {
        elem.classList.remove("selected_card");
      }
    }

    function click_handler(event) {
      window.location.href='http://click/'+this.id; return false;
    }
        
    function div_clickable(clickable) {
      elems = document.getElementsByClassName("card");
      for(var i = 0; i < elems.length; i++) {
        if (clickable) {
          elems[i].onclick = click_handler;
        } else {
          elems[i].onclick = null;
        }
      }
    }
    
    function set_order(card_id, order_no) {
      elem = document.getElementById(card_id);
      elem.style.order = order_no;
    }

    function get_checkboxes(card_id) {
      checkbox_states = '';
      elem = document.getElementById(card_id);
      checks = elem.getElementsByTagName("input"); 
      for (var i = 0; i < checks.length; i++) { 
        if (checks[i].checked) {
          checkbox_states += 'T';
        } else {
          checkbox_states += 'F';
        }
      }
      return checkbox_states;
    }
		
    function check_for_replace(target) {
      var sel = window.getSelection();
      var rng = sel.getRangeAt(0);
      if (rng.collapsed) {
        var replaced = false;
        var node = rng.endContainer;
        var parentNode = node.parentNode;
        var txt = node.textContent;
        if (txt == String.fromCharCode(42,160)) {
          parentNode.innerHTML = "<ul><li></ul>";
          replaced = true;
        } 49,46,160
        if (txt == String.fromCharCode(49,46,160)) {
          parentNode.innerHTML = "<ol><li></ol>";
          replaced = true;
        }
        if (replaced) {
          var targetNode = parentNode.firstChild.firstChild;
          var targetRange = new Range();
          targetRange.selectNodeContents(targetNode);
          sel.empty();
          sel.addRange(targetRange);
        } else {
          var beforePart = txt.substring(0, rng.endOffset)
          if (beforePart.endsWith("|_|")) {
            document.execCommand("delete");
            document.execCommand("delete");
            document.execCommand("delete");
            card_id = target.parentNode.id;
            html = "<input type=\\"checkbox\\"/>";
            document.execCommand("insertHTML", false, html);
          }
          if (beforePart.endsWith("|x|")) {
            document.execCommand("delete");
            document.execCommand("delete");
            document.execCommand("delete");
            card_id = target.parentNode.id;
            html = "<input type=\\"checkbox\\" checked=\\"true\\"/>";
            document.execCommand("insertHTML", false, html);
          }
        }
      }
    }
    
    function get_scroll_offset() {
      return document.body.scrollLeft + "," + document.body.scrollTop;
    }
    
    function set_scroll_offset(scroll_x, scroll_y) {
      document.body.scrollLeft = scroll_x;
      document.body.scrollTop = scroll_y;
    }
    
  </script>
  <style type="text/css">
    body {
      font-size: $font_size;
      #max-height: 120%;
    }
  
    .card {
      font-family: Arial;
      width: $card_width;
      border: 1px solid gray;
      box-shadow: 1px 1px 3px #888;
      border-top: 10px solid green;
      min-height: 50px;
      padding: 10px;
      margin: 10px;
    }
    
    .section {
      background-color: #eeffee;
    }
    
    .touch-transparent {
      pointer-events: none;
    }
    
    .selected_card {
      border-top: 10px solid red;
    }
    
    #mainbox {
      #font-family: calibri;
      max-height: 120%;
      box-sizing: border-box;
      justify-content: center;
      display: flex;
      flex-direction: column;
      flex-wrap: wrap;
    }
    
    h1 {
      font-size: 24px;
      #font-weight: lighter;
      #margin-left: 100px;
      #margin-top: -70px;
    }
    
    h1 a {
      text-decoration: none;
      color: black;
    }
    
    p {
      margin: 10px;
      #font-family: segoe ui;
      #line-height: 1.4em;
    }
  </style>
</head>
<body onload="initialize();">
<div id="mainbox">
  $cards
</div>
</body>
''')

card_template = Template('''
<div class="card$section_class" id="$id" style="order: $order">
  <h1><span class="card_title" contenteditable="true" onblur="window.location.href='http://blur/$id'; return false;">$title</span></h1>
  <div class="card_content" contenteditable="true" oninput="check_for_replace(event.target);" onblur="window.location.href='http://blur/$id'; return false;">$content</div>
</div>
''')

def get_note_from_page(webview, id):
  title_js = f'el = document.getElementById("{id}"); el.getElementsByClassName("card_title")[0].innerHTML;'
  content_js = f'el = document.getElementById("{id}"); el.getElementsByClassName("card_content")[0].innerHTML;'
  title = webview.evaluate_javascript(title_js)
  content = webview.evaluate_javascript(content_js)
  return (title, content)

selected_id = None

class Delegate():
  
  scroll_pos = (0,0)
  
  def webview_should_start_load(self, webview, url, nav_type):
    global selected_id
    
    if url == 'about:blank':
      return True
      
    if url.startswith('http://blur/'):
      id = url[url.rfind('/')+1:]
      (title, content) = get_note_from_page(webview, id)
      update_local_note(id, title, content)
      return False
      
    if url.startswith('http://click/'):
      id = url[url.rfind('/')+1:]
      if not selected_id:
        selected_id = id
        webview.eval_js(f'highlight_elem("{id}", true);')
      else:
        if selected_id != id:
          move_card(selected_id, id)
        webview.eval_js(f'highlight_elem("{selected_id}", false);')
        selected_id = None
      return False
      
    if url.startswith('ios-log:'):
      print(urllib.parse.unquote(url[len('ios-log:'):]))
      return False
      
    if url.startswith('http:') or url.startswith('https:'):
      url = 'safari-' + url
      
    webbrowser.open(url)
    return False
    
  def webview_did_finish_load(self, webview):
    x,y = self.scroll_pos
    webview.eval_js(f'set_scroll_offset({x},{y});')
    
def move_card(id, front_of_id):
  order_list = local_management['order']
  index1 = order_list.index(id)
  del order_list[index1]
  index2 = order_list.index(front_of_id)
  order_list.insert(index2, id)
  local_management['order'] = order_list
  for i, id in enumerate(order_list):
    v.eval_js(f'set_order("{id}", {i});')

checkbox_re = re.compile(r'<input type="checkbox"[^>]*>')

def update_local_note(id, title, content):
  prev_version = local_storage[id]
  checkboxes = v.eval_js(f'get_checkboxes("{id}");')
  for state in checkboxes:
    content = checkbox_re.sub(todo_true if state == 'T' else todo_false, content, 1)
  if prev_version['title'] != title or prev_version['content'] != content:
    dirty_queue.put_nowait(id)
    #print(dirty_queue.qsize())
    to_local_store(id, title, content, prev_version['section'])
    v['MenuButton'].background_color = nice_red

def show_menu(sender):
  local_dirty_count = len(local_management['dirty'])
  # local_dirty_message = f'{local_dirty_count} local changes' if local_dirty_count > 0 else 'No local changes'
  try:
    if local_dirty_count > 0:
      response = console.alert('Evernote sync', f'{local_dirty_count} local changes', 'Load all from server', 'Sync from server', 'Synchronize')
    else:
      response = console.alert('Evernote sync', 'No local changes', 'Load all from server', 'Sync from server')
    if response == 1:
      load_from_evernote(all_notes=True)
    if response == 2:
      load_from_evernote(all_notes=False)
    if response == 3:
      send_locals_to_server()
      load_from_evernote(all_notes=False)
    update_view()
  except KeyboardInterrupt: pass

async def send_locals_to_server():
  dirties = local_management['dirty']
  #count = len(dirties)
  for id in dirties:
    local_note = local_storage[id]
    note = {
      'id': id,
      'title': local_note['title'],
      'content': local_note['content']
    }
    update_count = await aui.post('http://127.0.0.1/update_note', {'note': note})
  local_management['dirty'] = {}
  v['MenuButton'].background_color = nice_green
  #console.hud_alert(f'{count} local changes sent to server')
  
async def check_and_update_from_remote():
  remote_dirty = False
  local_update_count = 0 if 'update_count' not in local_management else local_management['update_count']
  remote_update_count = (await aui.get('http://127.0.0.1/get_sync_state'))['update_count']
  if local_update_count < remote_update_count:
    notes = (await aui.get(f'http://127.0.0.1/get_filtered_sync_chunk/{local_update_count}'))['notes']
    await dirties_queue_to_local()
    dirties = local_management['dirty']
    for note_meta in notes:
      id, active = note_meta['guid'], note_meta['active']
      if id in dirties:
        continue
      if not active:
        if id in local_storage:
          del local_storage[id]
          remote_dirty = True
        continue
      note = await aui.get(f'http://127.0.0.1/get_note/{id}')
      (title, content, section) = (note['title'], note['content'], note['section'])
      if id not in local_storage:
        to_local_store(id, title, content, section)
        remote_dirty = True
        continue
      local_note = local_storage[id]
      if local_note['title'] != title or local_note['content'] != content or local_note['section'] != section:
        to_local_store(id, title, content, section)
        remote_dirty = True
    local_management['update_count'] = remote_update_count
    if remote_dirty:
      show(v['MenuButton'])
    

def create_menu_button(parent, show_menu_func, position=2, name='MenuButton', image_name='emj:Checkmark_1', color=(1,1,1,0.8), hidden=False, tint=True, tint_color='black'):
  b = ui.Button(name=name)
  b.image = ui.Image(image_name)
  if not tint:
    b.image = b.image.with_rendering_mode(ui.RENDERING_MODE_ORIGINAL)
  b.tint_color = tint_color
  b.background_color = color
  b.hidden = hidden
  d = 40
  b.width = b.height = d
  b.corner_radius = 0.5 * d
  if position > 0:
    b.x = parent.width - 1.5 * d
    b.y = parent.height - position * 1.5 * d
  else:
    b.x = parent.width + position * 1.5 * d
    b.y = parent.height - 1.5 * d
  
  b.action = show_menu_func
  parent.add_subview(b)

aui = asyncui.AsyncUIView()
aui.present(hide_title_bar=True)

dirty_queue = aui.create_queue()

v = ui.WebView(flex='WH')
v.delegate = Delegate()
aui.add_subview(v)
v.frame=aui.bounds

if iphone:
	frame = (-0.25*v.width,(v.height-v.width/1.2)/2,v.width*1.5,v.width/1.2)
else:
	frame = (0, 0, v.width, v.height)
d = ui.WebView(frame=frame, flex='WH', background_color='transparent')
d.hidden = True
if iphone:
	d.transform = ui.Transform.rotation(math.pi/2).concat(ui.Transform.scale(1.2, 1.2))

pinning = False

@script
def show_remote_updates(sender):
  update_view()
  hide(sender)

@script
def pin_notes(sender):
  global pinning, selected_id
  pinning = pinning == False
  sender.background_color = 'green' if pinning else 'grey'
  if pinning:
    hide_except_me(sender)
    #hide(v['MenuButton'])
    #hide(v['RollButton'])
    v.eval_js('make_editable(false);')
  else:
    show_except_me(sender)
    #show(v['MenuButton'])
    #show(v['RollButton'])
    v.eval_js('make_editable(true);')
    if selected_id:
      v.eval_js(f'highlight_elem("{selected_id}", false);')
      selected_id = None
 
@script 
def hide_except_me(me):
  for view in v.subviews:
    if view != me and type(view) == Button:
      hide(view)
  
@script 
def show_except_me(me):
  for view in v.subviews:
    if view != me and type(view) == Button:
      show(view)
  
@script
def add_note(sender):
  toggle_menu(sender)
  
@script
def show_dice(sender):
  d.alpha=0
  d.hidden=False
  show(d)
  hide(v['ShowMenuButton'])
  hide(v['RollButton'])  
  #hide(v['MoveButton'])  
  d.evaluate_javascript("$t.raise_event($t.id('throw'), 'mouseup');")
    
@script
def hide_dice(sender):
  hide(d)
  show(v['ShowMenuButton'])
  show(v['RollButton'])
  #show(v['MoveButton'])

overlay = ui.Button(frame=(0,0,d.width,d.height), flex='WH', background_color='transparent')
overlay.action = hide_dice
d.add_subview(overlay)

#m = MenuView()
#m.background_color = 'red'
#m.alpha = 0.0
#m.hidden = True

#v.add_subview(m)

create_menu_button(v, show_remote_updates, position=3, color=nice_red, hidden=True, tint=True)

local_storage = ReminderStore(namespace=reminder_namespace, to_json=True, cache=False)
local_management = ReminderStore(namespace=management_namespace, to_json=True, cache=False)

if 'dirty' in local_storage:
  local_management['dirty'] = local_storage['dirty']
  del local_storage['dirty']
if 'order' in local_storage:
  local_management['order'] = local_storage['order']
  del local_storage['order']

if 'dirty' not in local_management:
  load_all_from_evernote()
if 'order' not in local_management:
  local_management['order'] = [ id for id in local_storage ]

def update_view():
  scroll_pos = v.eval_js("get_scroll_offset();")
  if len(scroll_pos) > 0:
    v.delegate.scroll_pos = scroll_pos.split(',')
  
  card_html = ''

  order_list = local_management['order']
  for id in local_storage:
    if id not in order_list:
      order_list.append(id)
  local_management['order'] = order_list

  order = 0
  removed = []
  section_on = True
  for id in local_management['order']:
    note = local_storage[id]
    if not note:
      removed.append(id)
      continue
    if note['section']:
      section_on = section_on == False

    checkbox_true = '<input type="checkbox" checked="true"/>'
    checkbox_false = '<input type="checkbox"/>'
    
    note_content = note['content']   
    note_content = note_content.replace(todo_false, checkbox_false)
    note_content = note_content.replace(todo_true, checkbox_true)
    card_html += card_template.safe_substitute(id=id, title=note['title'], content=note_content, order=order, section_class=' section' if section_on else '')
    order += 1
  cleaned_list = [id for id in local_management['order'] if id not in removed]
  local_management['order'] = cleaned_list
  #if 'dirty' in local_management and len(local_management['dirty']) > 0:
  #v['MenuButton'].background_color = 'red'
    
  card_width = str(280 if iphone else 450) + 'px'
  font_size = str(12 if iphone else 18) + 'px'
  main_html = main_template.safe_substitute(cards=card_html, card_width=card_width, font_size=font_size)
  v.load_html(main_html)
  
update_view()

menu_open = False
menu_buttons = ['DeleteButton','AddButton','MoveButton']

@script
def toggle_menu(sender):
  global menu_open
  menu_speed = 0.5
  menu_open = menu_open == False
  menu_btn = v['ShowMenuButton']
  menu_location = menu_btn.center
  if menu_open:
    rotate_by(menu_btn, -90, duration=menu_speed)
    slide_color(menu_btn, 'background_color', (1,1,1,0.4), duration=menu_speed)
    for button_name in menu_buttons:
      btn = v[button_name]
      target_location = btn.center
      btn.center = menu_location
      show(btn, duration=menu_speed)
      roll_to(btn, target_location, duration=menu_speed)
    yield
  else:
    locations = {}
    rotate_by(menu_btn, 90, duration=menu_speed)
    slide_color(menu_btn, 'background_color', 'white', duration=menu_speed)
    for button_name in menu_buttons:
      btn = v[button_name]
      locations[button_name] = btn.center
      hide(btn, duration=menu_speed)
      roll_to(btn, menu_location, end_right_side_up=False, duration=menu_speed)
    yield
    for button_name in menu_buttons:
      btn = v[button_name]
      btn.center = locations[button_name]

create_menu_button(v, show_dice, position=2, name='RollButton', image_name='d10.png')

create_menu_button(v, pin_notes, position=-4, name='DeleteButton', image_name='iob:ios7_minus_empty_256', color=nice_red, hidden=True, tint=True, tint_color='white')

create_menu_button(v, add_note, position=-3, name='AddButton', image_name='iob:ios7_plus_empty_256', color=nice_green, hidden=True, tint=True, tint_color='white')

create_menu_button(v, pin_notes, position=-2, name='MoveButton', image_name='pin.png', hidden=True)

create_menu_button(v, toggle_menu, position=1, name='ShowMenuButton', image_name='wrench.png')

v['RollButton'].transform = Transform.rotation(math.radians(45))

v.add_subview(d)
d.load_url(os.path.abspath('dice/dice/index.html'))

_make_webview_transparent(d)

server = evernoteproxy.MyWSGIRefServer(port=80)
  
threading.Thread(group=None, target=evernoteproxy.app.run, name=None, args=(), kwargs={'server': server, 'quiet': False}).start()

async def check_loop(checks):
  if checks is None:
    checks = 0
  await dirties_queue_to_local()
  if len(local_management['dirty']) > 0:
    await send_locals_to_server()
  checks += 1
  if checks == 10:
    checks = 0
    await check_and_update_from_remote()
  return checks
  
async def dirties_queue_to_local():
  while not dirty_queue.empty():
    id = dirty_queue.get_nowait()
    dirties = local_management['dirty']
    dirties[id] = True
    local_management['dirty'] = dirties
    
aui.call_every_loop = check_loop
aui.loop_delay = 5

try:
  aui.start_loop()
finally:
  server.stop()