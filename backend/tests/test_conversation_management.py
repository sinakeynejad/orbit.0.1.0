import sqlite3
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.core.config import Settings
from app.memory.store import Store
from app.memory.conversation import Conversation
from app.llm.schemas import Message, MessageRole
from tests.test_api import TOKEN, ReplyProvider


def test_rename_search_export(tmp_path):
    config=Settings(_env_file=None,api_token=TOKEN,workspace_dir=tmp_path,data_dir=tmp_path)
    headers={"Authorization":"Bearer "+TOKEN}
    with TestClient(create_app(config,ReplyProvider())) as client:
        sid=client.post("/sessions",headers=headers).json()["session_id"]
        assert client.patch('/sessions/'+sid,json={"title":"Private"}).status_code==401
        assert client.get('/sessions/'+sid+'/export').status_code==401
        client.post('/sessions/'+sid+'/messages',headers=headers,json={"message":"Unique content سلام"})
        assert client.patch('/sessions/'+sid,headers=headers,json={"title":"  My notes  "}).json()["title"]=="My notes"
        assert client.get('/sessions?q=MY%20NOTES',headers=headers).json()[0]["id"]==sid
        assert client.get('/sessions?q=unique',headers=headers).json()[0]["id"]==sid
        assert client.get('/sessions?q=missing',headers=headers).json()==[]
        assert client.patch('/sessions/'+sid,headers=headers,json={"title":"   "}).status_code==400
        assert client.patch('/sessions/'+sid,headers=headers,json={"title":"x"*101}).status_code==422
        result=client.get('/sessions/'+sid+'/export',headers=headers)
        assert result.status_code==200
        assert result.headers['content-type'].startswith('text/markdown')
        assert '# My notes' in result.text and 'سلام' in result.text and '## Orbit' in result.text
        assert 'You are a desktop assistant' not in result.text
        assert client.get('/sessions/unknown/export',headers=headers).status_code==400
        assert client.patch('/sessions/unknown',headers=headers,json={"title":"Name"}).status_code==400


def test_title_migration_and_persistence(tmp_path):
    path=tmp_path/'history.sqlite3'
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, turns TEXT)')
    db.execute("INSERT INTO sessions VALUES ('old','New conversation','[]')")
    db.commit();db.close()
    store=Store(path)
    assert store.load()['old'].title=='New conversation'
    conv=Conversation();conv.custom_title='نام دلخواه'
    store.save('new',conv);store.close()
    store=Store(path);conv=store.load()['new']
    conv.commit([Message(role=MessageRole.USER,content='New message')])
    store.save('new',conv);store.close()
    store=Store(path)
    assert store.load()['new'].title=='نام دلخواه'
    store.close()
