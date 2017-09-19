# coding: utf-8

# Import Evernote auth_token, notebook_guid and ReminderStore reminder_namespace
from noterconf import *

# Using Evernote Python SDK from 
# Copy evernote and thrift from lib to site-packages
#import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.type.ttypes as Types
from evernote.edam.notestore.ttypes import NoteFilter, NotesMetadataResultSpec
from evernote.api.client import EvernoteClient

from ReminderStore import ReminderStore
from scripter import *

import ui, console, webbrowser

import json, functools, re, os, math
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
      clear_color = ObjCClass('UIColor').clearColor()
        
spin = ui.ActivityIndicator()

note_syntax = ('<?xml version="1.0" encoding="UTF-8" standalone="no"?>', '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">', '<en-note>', '</en-note>', '<?xml version="1.0" encoding="UTF-8"?>')

client = EvernoteClient(token=auth_token, sandbox=False)
note_store = client.get_note_store()
user = client.get_user_store().getUser(auth_token)
userId = user.id
shardId = user.shardId

filter = NoteFilter(notebookGuid=notebook_guid, order=Types.NoteSortOrder.TITLE)

# List all of the notebooks in the user's account
#notebooks = note_store.listNotebooks()
#print("Found ", len(notebooks), " notebooks:")
#for notebook in notebooks:
#  print("  * ", notebook.name, notebook.guid)

def load_all_from_evernote():
  spin.start()
  rexp = r'(<[^>]+) style=".*?"'
  pr = re.compile(rexp, re.IGNORECASE)
  local_storage['dirty'] = {}
  local_keys = dict.fromkeys(local_storage, True)
  del local_keys['dirty']
  v['MenuButton'].background_color = 'green'
  notes = note_store.findNotesMetadata(filter, 0, 1000, NotesMetadataResultSpec())
  for note_data in reversed(notes.notes):
    if note_data.guid in local_keys:
      del local_keys[note_data.guid]
    note = note_store.getNote(note_data.guid, True, False, False, False)
    stripped_content = note.content
    #print('-'*50)
    #print(cntnt)
    #orig_content = cntnt[cntnt.find('>')+1:]
    #soup = BeautifulSoup(orig_content, "html5lib")
    #for tag in soup():
      #for attribute in ["class", "id", "name", "style"]:
        #del tag[attribute]
    #stripped_content = str(soup)
    #if not cntnt.startswith(preamble):

    #cntnt = cntnt[len(preamble):]
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
    #print(stripped_content)
    #note_link = f'evernote:///view/{userId}/{shardId}/{note_data.guid}/{note_data.guid}/'
    to_local_store(note_data.guid, note.title, stripped_content)
  for  id in local_keys:
    del local_storage[id]
  spin.stop()
  console.hud_alert('Updated from server')
    
def to_local_store(id, title, content):
  local_storage[id] = {
    'title': title,
    'content': content,
  }

main_template = Template('''
<html>
<head>
  <meta name="viewport" content="height=device-height, initial-scale=0.8">
  <style type="text/css">
    body {
      font-size: 12px;
      #max-height: 120%;
    }
  
    .card {
      font-family: Arial;
      width: 280px;
      border: 1px solid gray;
      box-shadow: 1px 1px 3px #888;
      border-top: 10px solid green;
      min-height: 50px;
      padding: 10px;
      margin: 10px;
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
      font-size: 16px;
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
<body > <!-- onload="initialize();" -->
<div id="mainbox">
  $cards
</div>
</body>
''')

card_template = Template('''
<div class="card" id="$id">
  <h1><span class="title" contenteditable="true" onblur="window.location.href='http://blur/$id'; return false;">$title</span></h1>
  <div class="content" contenteditable="true" onblur="window.location.href='http://blur/$id'; return false;">$content</div>
</div>
''')

def get_note_from_page(webview, id):
  title_js = f'el = document.getElementById("{id}"); el.getElementsByClassName("title")[0].innerHTML;'
  content_js = f'el = document.getElementById("{id}"); el.getElementsByClassName("content")[0].innerHTML;'
  title = webview.evaluate_javascript(title_js)
  content = webview.evaluate_javascript(content_js)
  return (title, content)

class Delegate():
  def webview_should_start_load(self, webview, url, nav_type):
    if url == 'about:blank':
      return True
    if url.startswith('http://blur/'):
      id = url[url.rfind('/')+1:]
      (title, content) = get_note_from_page(webview, id)
      update_local_note(id, title, content)
      #print('UPDATE:')
      #print(content)
      return False
    if url.startswith('http:') or url.startswith('https:'):
      url = 'safari-' + url
    webbrowser.open(url)
    return False

def update_local_note(id, title, content):
  prev_version = local_storage[id]
  if prev_version['title'] != title or prev_version['content'] != content:
    dirties = local_storage['dirty']
    dirties[id] = True
    local_storage['dirty'] = dirties
    to_local_store(id, title, content)
    v['MenuButton'].background_color = 'red'

def show_menu(sender):
  local_dirty_count = len(local_storage['dirty'])
  local_dirty_message = f'{local_dirty_count} local changes' if local_dirty_count > 0 else 'No local changes'
  try:
    if local_dirty_count > 0:
      response = console.alert('Evernote sync', f'{local_dirty_count} local changes', 'Load all from server', 'Upload local changes')
    else:
      response = console.alert('Evernote sync', 'No local changes', 'Load all from server')
    if response == 1:
      load_all_from_evernote()
      update_view()
    if response == 2:
      send_locals_to_server()
  except KeyboardInterrupt: pass

def send_locals_to_server():
  spin.start()
  dirties = local_storage['dirty']
  count = len(dirties)
  for id in dirties:
    local_note = local_storage[id]
    ever_note = Types.Note()
    ever_note.guid = id
    ever_note.title = local_note['title']
    cntnt = re.sub(r'<br>', r'<br/>', local_note['content'])
    ever_note.content = ''.join(note_syntax[0:3]) + cntnt + note_syntax[3]
    #print('_'*40)
    #print(ever_note.content)
    try:
      note_store.updateNote(ever_note)
    except Exception as e:
      print(e)
      raise e
  local_storage['dirty'] = {}
  v['MenuButton'].background_color = 'green'
  console.hud_alert(f'{count} local changes sent to server')
  spin.stop()

def create_menu_button(parent, show_menu_func, position=1, name='MenuButton', image_name='emj:Cloud', color='green'):
  b = ui.Button(name=name)
  b.image = ui.Image(image_name).with_rendering_mode(ui.RENDERING_MODE_ORIGINAL)
  b.tint_color = 'white'
  b.background_color = color
  b.alpha = 0.7
  d = 40
  b.width = b.height = d
  b.corner_radius = 0.5 * d
  b.x = parent.width - 1.5 * d
  b.y = parent.height - position * 1.5 * d
  
  b.action = show_menu_func
  parent.add_subview(b)

v = ui.WebView()
v.delegate = Delegate()
v.present(hide_title_bar=True)
v.add_subview(spin)
spin.style = ui.ACTIVITY_INDICATOR_STYLE_GRAY

d = ui.WebView(frame=(-0.25*v.width,(v.height-v.width/1.2)/2,v.width*1.5,v.width/1.2), flex='WH', background_color='transparent')
d.hidden = True
d.transform = ui.Transform.rotation(math.pi/2).concat(ui.Transform.scale(1.2, 1.2))

@script
def show_dice(sender):
  d.alpha=0
  d.hidden=False
  show(d)
  hide(v['MenuButton'])
  hide(v['RollButton'])  
  d.evaluate_javascript("$t.raise_event($t.id('throw'), 'mouseup');")
    
@script
def hide_dice(sender):
  hide(d)
  show(v['MenuButton'])
  show(v['RollButton'])

overlay = ui.Button(frame=(0,0,d.width,d.height), flex='WH', background_color='transparent')
overlay.action = hide_dice
d.add_subview(overlay)

#m = MenuView()
#m.background_color = 'red'
#m.alpha = 0.0
#m.hidden = True

#v.add_subview(m)

create_menu_button(v, show_menu)

local_storage = ReminderStore(namespace=reminder_namespace, to_json=True, cache=False)

if 'dirty' not in local_storage:
  load_all_from_evernote()

def update_view():
  card_html = ''
  for id in local_storage:
    if id == 'dirty': continue
    note = local_storage[id]
    card_html += card_template.safe_substitute(id=id, title=note['title'], content=note['content'])
  if 'dirty' in local_storage and len(local_storage['dirty']) > 0:
    v['MenuButton'].background_color = 'red'
    
  main_html = main_template.safe_substitute(cards=card_html)
  
  v.load_html(main_html)
  
update_view()

create_menu_button(v, show_dice, position=2, name='RollButton', image_name='emj:Game_Die', color='blue')

v.add_subview(d)
d.load_url(os.path.abspath('dice/dice/index.html'))

_make_webview_transparent(d)
