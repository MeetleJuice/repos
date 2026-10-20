"""Bounded local-only NDJSON/SSE transport. No background request workers."""
from __future__ import annotations
import http.client
import json
import threading
import time
from typing import Any, Callable
import urllib.error
import urllib.request
from . import __version__
from .http_io import MAX_RESPONSE_BYTES
from .models import ModelError, NoLocalRedirect


def stream_chat(url: str, payload: dict[str, Any], headers: dict[str,str], timeout: int,
                provider: str, cancel: threading.Event, progress: Callable[[str],None]) -> dict[str,Any]:
    if cancel.is_set():raise InterruptedError('Stopped before local streaming.')
    request=urllib.request.Request(url,data=json.dumps({**payload,'stream':True}).encode(),
        headers={'Content-Type':'application/json','User-Agent':'IdeaFoundry/'+__version__+' desktop-client',**headers})
    result: dict[str,Any]={};parts: list[str]=[];terminal=False;buffer=b'';size=0
    deadline=time.monotonic()+timeout

    def consume(line: bytes) -> None:
        nonlocal terminal,result
        if cancel.is_set():raise InterruptedError('Stopped. Partial local response discarded.')
        line=line.strip()
        if not line or line.startswith(b':') or line.startswith(b'event:'):return
        if provider=='local':
            if not line.startswith(b'data:'):return
            line=line[5:].strip()
            if line==b'[DONE]':return
        frame=json.loads(line)
        if not isinstance(frame,dict) or frame.get('error'):raise ModelError('Local runtime rejected the streaming request. Check its model and context settings.','request')
        if provider=='ollama':
            message=frame.get('message',{})
            text=message.get('content','') if isinstance(message,dict) else ''
            if frame.get('done') is True:terminal=True;result=frame
        else:
            if isinstance(frame.get('usage'),dict):result['usage']=frame['usage']
            choices=frame.get('choices',[])
            choice=choices[0] if isinstance(choices,list) and choices and isinstance(choices[0],dict) else {}
            delta=choice.get('delta',{})
            text=delta.get('content','') if isinstance(delta,dict) else ''
            if choice.get('finish_reason'):
                terminal=True;result['choices']=[{'finish_reason':choice['finish_reason']}]
            if isinstance(frame.get('model'),str):result['model']=frame['model']
        if text is not None and not isinstance(text,str):raise ModelError('Local stream contained non-text output.','format')
        if text:parts.append(text);progress(text)

    try:
        # Loopback services must not be sent through an injected HTTP proxy or redirect.
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoLocalRedirect())
        with opener.open(request,timeout=timeout) as response:
            reader=getattr(response,'read1',response.read)
            while True:
                if cancel.is_set():raise InterruptedError('Stopped. Partial local response discarded.')
                if time.monotonic()>=deadline:raise TimeoutError()
                chunk=reader(min(65536,MAX_RESPONSE_BYTES+1-size))
                if cancel.is_set():raise InterruptedError('Stopped. Partial local response discarded.')
                if time.monotonic()>=deadline:raise TimeoutError()
                if not chunk:break
                size+=len(chunk)
                if size>MAX_RESPONSE_BYTES:raise ModelError('Local stream exceeded 2 MB. Split the task.','size')
                buffer+=chunk
                while b'\n' in buffer:
                    line,buffer=buffer.split(b'\n',1);consume(line)
            if buffer:consume(buffer)
    except urllib.error.HTTPError as exc:
        status=exc.code;exc.close()
        raise ModelError('Local runtime returned HTTP '+str(status)+'. Check its loaded model, authentication and context settings.',
                         'auth' if status in {401,403} else 'request' if status==400 else 'provider',http_status=status) from None
    except InterruptedError:
        raise
    except (TimeoutError,OSError,http.client.HTTPException):
        raise ModelError('Local streaming connection timed out or disconnected. Check the selected runtime; partial output was not saved.','transport') from None
    except (json.JSONDecodeError,UnicodeDecodeError):
        raise ModelError('Local runtime returned a malformed streaming frame.','format') from None
    if not terminal:raise ModelError('Local stream ended without a completion marker; partial output was not accepted.','format')
    content=''.join(parts)
    if provider=='ollama':result['message']={'content':content}
    else:result['choices'][0]['message']={'content':content}
    return result
