from types import SimpleNamespace
from app import llm


def response(reply='ok', cache_hit=False):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))], usage=SimpleNamespace(prompt_tokens=7, completion_tokens=2), model='gemini/gemini-2.0-flash', _hidden_params={'cache_hit': cache_hit})


def test_simulated_429_advances_to_second_key(monkeypatch):
    monkeypatch.setattr(llm.settings, 'llm_api_keys', 'first,second')
    calls=[]
    monkeypatch.setattr(llm, 'litellm', SimpleNamespace(completion=lambda **kwargs: (calls.append(kwargs) or response())))
    result=llm.generate([{'role':'system','content':'sys'},{'role':'user','content':'hello'}], 'key_1=429')
    assert len(calls)==1 and calls[0]['api_key']=='second'
    assert result.metadata['key_id']=='key_2' and result.metadata['fallback_attempts']==1
    assert result.metadata['resolution_source']=='LIVE_INFERENCE'


def test_cache_hit_maps_metadata_and_hides_key(monkeypatch):
    monkeypatch.setattr(llm.settings, 'llm_api_keys', 'first,second')
    monkeypatch.setattr(llm, 'litellm', SimpleNamespace(completion=lambda **kwargs: response('cached reply', True)))
    result=llm.generate([{'role':'system','content':'sys'},{'role':'user','content':'hello'}])
    assert result.reply=='cached reply'
    assert result.metadata['resolution_source']=='LLM_CACHE'
    assert result.metadata['key_id'] is None and result.metadata['fallback_attempts']==0
    assert result.metadata['input_tokens']==7 and result.metadata['output_tokens']==2


def test_all_simulated_keys_fail_without_provider_call(monkeypatch):
    monkeypatch.setattr(llm.settings, 'llm_api_keys', 'first,second')
    def unexpected(**kwargs):
        raise AssertionError('provider must not be called')
    monkeypatch.setattr(llm, 'litellm', SimpleNamespace(completion=unexpected))
    try:
        llm.generate([{'role':'user','content':'hello'}], '*=429')
    except RuntimeError as exc:
        assert str(exc)=='all providers unavailable'
    else:
        raise AssertionError('expected all providers unavailable')
