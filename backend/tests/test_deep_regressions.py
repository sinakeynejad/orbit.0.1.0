import sqlite3
import httpx
import pytest
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.core.config import Settings
from app.core.exceptions import ProviderError, ToolError
from app.llm.providers.ollama import OllamaProvider
from app.llm.providers.openai import OpenAIProvider
from app.memory.store import Store
from app.memory.conversation import Conversation
from app.tools.files import FileTools
from tests.test_api import TOKEN, ReplyProvider


def test_saved_key_cannot_follow_changed_endpoint(tmp_path):
    config=Settings(_env_file=None,api_token=TOKEN,llm_provider="openai",llm_api_key="private-key",llm_model="test",workspace_dir=tmp_path,data_dir=tmp_path)
    with TestClient(create_app(config,ReplyProvider())) as client:
        result=client.put('/settings',headers={'Authorization':'Bearer '+TOKEN},json={'llm_provider':'openai','llm_model':'test','llm_base_url':'https://other.example/v1'})
        assert result.status_code==400
        assert client.app.state.config.llm_base_url is None
        assert 'private-key' not in result.text


@pytest.mark.parametrize('provider',[OllamaProvider,OpenAIProvider])
@pytest.mark.parametrize('data',[[],None,{'message':None,'choices':[{'finish_reason':'stop','message':None}]}])
async def test_bad_provider_shapes_are_controlled(provider,data):
    config=Settings(_env_file=None,llm_model='test',llm_api_key='test')
    async with httpx.AsyncClient(base_url='http://test/',transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data))) as client:
        with pytest.raises(ProviderError):await provider(config,client).generate([])


def test_one_corrupt_session_does_not_block_all_history(tmp_path):
    store=Store(tmp_path/'db.sqlite3');store.save('valid',Conversation())
    with store.db:store.db.execute("INSERT INTO sessions(id,title,turns) VALUES ('bad','bad','not-json')")
    assert 'valid' in store.load()
    assert store.db.execute("SELECT turns FROM sessions WHERE id='bad'").fetchone()[0]=='not-json'
    store.close()


def test_windows_trash_path_is_case_insensitive(tmp_path):
    with pytest.raises(ToolError):FileTools(tmp_path).resolve('.TRASH/private.txt')


def test_failed_persistence_keeps_session_state(tmp_path):
    config=Settings(_env_file=None,api_token=TOKEN,workspace_dir=tmp_path,data_dir=tmp_path)
    class BrokenStore:
        def save(self,*args):raise sqlite3.OperationalError('disk full')
        def delete(self,*args):raise sqlite3.OperationalError('disk full')
    with TestClient(create_app(config,ReplyProvider())) as client:
        assistant=client.app.state.assistant
        sid=assistant.create_session();assistant.store=BrokenStore()
        with pytest.raises(Exception):assistant.create_session()
        assert len(assistant.sessions)==1
        with pytest.raises(Exception):assistant.delete_session(sid)
        assert sid in assistant.sessions


@pytest.mark.parametrize('provider,url,expected',[('ollama',None,False),('openai','https://other.example/v1',False),('openai',None,True)])
def test_voice_does_not_reuse_other_service_credentials(provider,url,expected):
    settings=Settings(_env_file=None,llm_provider=provider,llm_base_url=url,llm_api_key='model-key')
    assert bool(settings.speech_api_key) is expected
    explicit=Settings(_env_file=None,llm_provider=provider,llm_base_url=url,llm_api_key='model-key',voice_api_key='voice-key')
    assert explicit.speech_api_key.get_secret_value()=='voice-key'
