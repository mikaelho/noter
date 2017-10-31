#coding: utf-8
import bottle, json, re
auth_token = None
from noterconf import *

import evernote.edam.type.ttypes as Types
from evernote.edam.notestore.ttypes import NoteFilter, SyncChunkFilter,  NotesMetadataResultSpec
from evernote.api.client import EvernoteClient

note_syntax = ('<?xml version="1.0" encoding="UTF-8" standalone="no"?>', '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">', '<en-note>', '</en-note>', '<?xml version="1.0" encoding="UTF-8"?>')

rexp = r'(<[^>]+) style=".*?"'
pr = re.compile(rexp, re.IGNORECASE)

if auth_token:
  client = EvernoteClient(token=auth_token, sandbox=False)
  note_store = client.get_note_store()
  user = client.get_user_store().getUser(auth_token)
  
  userId = user.id
  shardId = user.shardId
  
class MyWSGIRefServer(bottle.ServerAdapter):
  server = None

  def run(self, handler):
    from wsgiref.simple_server import make_server, WSGIRequestHandler
    if self.quiet:
      class QuietHandler(WSGIRequestHandler):
        def log_request(*args, **kw): pass
      self.options['handler_class'] = QuietHandler
    self.server = make_server(self.host, self.port, handler, **self.options)
    self.server.serve_forever()

  def stop(self):
    self.server.shutdown()
    
class EvernoteProxy(bottle.Bottle):
  
  def __init__(self, *args, **kwargs):
    super().__init__(self, *args, **kwargs)
    self.client = EvernoteClient(token=auth_token, sandbox=False)
    self.note_store = self.client.get_note_store()
    self.user = self.client.get_user_store().getUser(auth_token)
    
    self.userId = user.id
    self.shardId = user.shardId
    
app = EvernoteProxy()
    
@app.get
def get_sync_state():
  current_state = app.note_store.getSyncState()
  return { 'update_count': current_state.updateCount }
  
@app.get
def get_filtered_sync_chunk(update_count):
  update_count = int(update_count)
  filter = SyncChunkFilter(includeNotes=True) 
  sync_chunk = app.note_store.getFilteredSyncChunk(update_count, 10000, filter)
  notes = [{ 'guid': note.guid, 'title': note.title, 'active': note.active} for note in sync_chunk.notes if note.notebookGuid==notebook_guid]
  return {'notes': notes}
    
@app.post
def create_note():
  note = bottle.request.json['note']
  ever_note = Types.Note()
  ever_note.title = note['title']
  cntnt = re.sub(r'<br>', r'<br/>', note['content'])
  ever_note.content = ''.join(note_syntax[0:3]) + cntnt + note_syntax[3]
  ever_note.notebookGuid = notebook_guid
  ever_note_meta = app.note_store.createNote(ever_note)
  return {
    'updateCount': ever_note_meta.updateSequenceNum, 
    'id': ever_note_meta.guid
  }
  
@app.get
def get_note(id):
  note = app.note_store.getNote(id, True, False, False, False)
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
  return {
    'id': note.guid,
    'title': note.title,
    'content': stripped_content,
    'section': note.tagGuids is not None
  }
  
@app.post
def update_note():
  note = bottle.request.json['note']
  ever_note = Types.Note()
  ever_note.guid = note['id']
  ever_note.title = note['title']
  cntnt = re.sub(r'<br>', r'<br/>', note['content'])
  ever_note.content = ''.join(note_syntax[0:3]) + cntnt + note_syntax[3]
  ever_note_meta = app.note_store.updateNote(ever_note)
  return { 'update_count': ever_note_meta.updateSequenceNum }
  
@app.get
def delete_note(id):
  update_count = app.note_store.deleteNote(id)
  return { 'update_count': update_count }

if __name__ == '__main__':
  import threading, time, requests
  
  server = MyWSGIRefServer(port=80)
  
  threading.Thread(group=None, target=app.run, name=None, args=(), kwargs={'server': server, 'quiet': False}).start()
  
  try:
    time.sleep(2)
    
    resp = requests.get('http://127.0.0.1/get_sync_state')
    upd_count = resp.json()['update_count']
    print('Upd', upd_count)
    
    note = {
      'title': 'Test note',
      'content': 'Test content'
    }
    resp = requests.post(f'http://127.0.0.1/create_note', json={ 'note': note })
    data = resp.json()
    print('Upd', data['updateCount'])
    
    note['id'] = data['id']
    note['title'] = 'Updated'
    
    resp = requests.post(f'http://127.0.0.1/update_note', json={ 'note': note })
    print('Upd', resp.json()['update_count'])
    
    resp = requests.get(f'http://127.0.0.1/get_note/{data["id"]}')
    print(resp.json())
    
    resp = requests.get(f'http://127.0.0.1/delete_note/{data["id"]}')
    print('Upd', resp.json()['update_count'])
    
    resp = requests.get(f'http://127.0.0.1/get_filtered_sync_chunk/{data["updateCount"]-1}')
    print([(note['title'], note['active']) for note in resp.json()['notes']])
  
  finally:
    server.stop()

