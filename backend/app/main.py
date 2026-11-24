from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from .config import settings
from .db import init_db, add_message, get_messages, session_exists, get_system_prompt, save_system_prompt, engine
from .llm import generate

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title='LYFTR LLM Chatbot', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins or [], allow_credentials=False, allow_methods=['GET','POST','OPTIONS'], allow_headers=['Content-Type','X-Simulate-Failure'])

@app.exception_handler(Exception)
async def safe_unhandled_error(request: Request, exc: Exception):
    # Keep internal tracebacks in server logs; never expose them to the client.
    return JSONResponse(status_code=500, content={'detail': 'internal server error'})

class ChatRequest(BaseModel):
    session_id: str
    message: str
    system_prompt: str | None = None

    @field_validator('session_id')
    @classmethod
    def valid_session(cls, value):
        value = value.strip()
        if not value or len(value) > 128:
            raise ValueError('session_id must be 1–128 characters after trimming')
        return value

    @field_validator('message')
    @classmethod
    def valid_message(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('message must not be empty')
        if len(value) > 4000:
            raise ValueError('message must be 1–4000 characters after trimming')
        return value

@app.get('/health')
def health():
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql('SELECT 1')
        if len(settings.keys) < 2:
            raise RuntimeError('At least two API keys are required')
        if not settings.llm_model:
            raise RuntimeError('LLM_MODEL is not configured')
        return {'status': 'ok', 'keys_configured': len(settings.keys), 'cache_enabled': True}
    except Exception as exc:
        raise HTTPException(status_code=503, detail='service not ready') from exc

@app.post('/chat')
def chat(payload: ChatRequest, x_simulate_failure: str | None = Header(default=None, alias='X-Simulate-Failure')):
    existing = get_messages(payload.session_id)
    stored_prompt = get_system_prompt(payload.session_id)
    system_prompt = (payload.system_prompt.strip() if payload.system_prompt is not None else (stored_prompt or settings.default_system_prompt)).strip()
    messages = [{'role':'system','content':system_prompt}]
    messages.extend({'role':m['role'], 'content':m['content']} for m in existing)
    messages.append({'role':'user','content':payload.message})
    try:
        result = generate(messages, x_simulate_failure)
    except RuntimeError as exc:
        if str(exc) == 'all providers unavailable' or 'API_KEYS' in str(exc) or 'LiteLLM' in str(exc):
            raise HTTPException(status_code=503, detail='all providers unavailable') from exc
        raise HTTPException(status_code=503, detail='all providers unavailable') from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail='all providers unavailable') from exc
    # Persist only after successful generation; failed calls never pollute history.
    save_system_prompt(payload.session_id, system_prompt)
    add_message(payload.session_id, 'user', payload.message)
    add_message(payload.session_id, 'assistant', result.reply, result.metadata)
    return {'session_id': payload.session_id, 'reply': result.reply, 'metadata': result.metadata}

@app.get('/sessions/{session_id}/messages')
def history(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail='session not found')
    return {'session_id': session_id, 'messages': get_messages(session_id)}
