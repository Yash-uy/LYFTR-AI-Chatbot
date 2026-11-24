import os
os.environ.setdefault('LLM_API_KEYS', 'test-key-one,test-key-two')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_app.db')
os.environ.setdefault('ENABLE_FAILURE_SIMULATION', 'true')
from fastapi.testclient import TestClient
from app.main import app
from app import main
from app.llm import GatewayResult


def setup_function():
    from app.db import engine, init_db
    init_db()
    with engine.begin() as conn:
        conn.exec_driver_sql('DELETE FROM messages')


def fake_result(reply='Test reply', source='LIVE_INFERENCE', key='key_1', attempts=0):
    return GatewayResult(reply, {'resolution_source':source,'model':'gemini/gemini-2.0-flash','latency_ms':4,'input_tokens':12,'output_tokens':3,'key_id':key,'fallback_attempts':attempts})


def test_health_contract():
    with TestClient(app) as client:
        response=client.get('/health')
        assert response.status_code==200
        assert response.json()=={'status':'ok','keys_configured':2,'cache_enabled':True}


def test_validation_rejects_blank_and_overlong():
    with TestClient(app) as client:
        assert client.post('/chat',json={'session_id':'s1','message':'   '}).status_code==422
        assert client.post('/chat',json={'session_id':'s1','message':'x'*4001}).status_code==422
        assert client.post('/chat',json={'session_id':'','message':'hi'}).status_code==422


def test_success_persists_user_and_assistant_and_history(monkeypatch):
    monkeypatch.setattr(main,'generate',lambda messages,header=None: fake_result())
    with TestClient(app) as client:
        response=client.post('/chat',json={'session_id':'session-a','message':'hello'})
        assert response.status_code==200
        assert response.json()['metadata']['resolution_source']=='LIVE_INFERENCE'
        history=client.get('/sessions/session-a/messages').json()['messages']
        assert [m['role'] for m in history]==['user','assistant']
        assert history[1]['metadata']['output_tokens']==3


def test_multiturn_history_sent_to_gateway(monkeypatch):
    observed=[]
    def fake(messages, header=None):
        observed.append(messages)
        return fake_result('remembered')
    monkeypatch.setattr(main,'generate',fake)
    with TestClient(app) as client:
        client.post('/chat',json={'session_id':'multi','message':'My name is Yash'})
        client.post('/chat',json={'session_id':'multi','message':'What is my name?'})
    assert [m['content'] for m in observed[1][-3:]]==['My name is Yash','remembered','What is my name?']


def test_failed_request_does_not_write_history(monkeypatch):
    monkeypatch.setattr(main,'generate',lambda messages,header=None: (_ for _ in ()).throw(RuntimeError('all providers unavailable')))
    with TestClient(app) as client:
        response=client.post('/chat',json={'session_id':'failed','message':'hello'})
        assert response.status_code==503
        assert response.json()=={'detail':'all providers unavailable'}
        assert client.get('/sessions/failed/messages').status_code==404


def test_unknown_session_404():
    with TestClient(app) as client:
        response=client.get('/sessions/does-not-exist/messages')
        assert response.status_code==404
        assert response.json()=={'detail':'session not found'}


def test_cache_and_fallback_metadata_contract(monkeypatch):
    # Gateway is isolated in these API tests; integration tests below exercise LiteLLM with keys.
    calls=[]
    def fake(messages, header=None):
        calls.append(header)
        if header=='key_1=429': return fake_result(key='key_2',attempts=1)
        if header=='*=429': raise RuntimeError('all providers unavailable')
        return fake_result(source='LLM_CACHE',key=None,attempts=0)
    monkeypatch.setattr(main,'generate',fake)
    with TestClient(app) as client:
        fallback=client.post('/chat',json={'session_id':'fallback','message':'hello'},headers={'X-Simulate-Failure':'key_1=429'})
        assert fallback.status_code==200 and fallback.json()['metadata']['key_id']=='key_2'
        fail=client.post('/chat',json={'session_id':'all-fail','message':'hello'},headers={'X-Simulate-Failure':'*=429'})
        assert fail.status_code==503
        cached=client.post('/chat',json={'session_id':'cache','message':'same'},headers={})
        assert cached.json()['metadata']['resolution_source']=='LLM_CACHE'
        assert cached.json()['metadata']['key_id'] is None
