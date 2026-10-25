"""No SDK dependency. HTTP happens ONLY when CLI receives --live."""
from __future__ import annotations
import http.client,json,os,time,urllib.error,urllib.request

class ProviderError(Exception):
    def __init__(self,message,status=None,retryable=False,raw=None):
        super().__init__(message)
        self.status=status;self.retryable=retryable;self.raw=raw;self.retry_after=None

class ModelMismatchError(RuntimeError):
    """A billed response was preserved, but its model identity requires review."""


def build_request(provider,model,system,user,max_output_tokens,temperature=None,*,effort=None,thinking=None):
    if provider=='anthropic':
        payload = {'model':model,'system':system,'messages':[{'role':'user','content':user}], 'max_tokens':max_output_tokens}
        if effort is not None:
            if effort not in ('low','medium','high','xhigh','max'):
                raise ValueError('Unsupported Anthropic effort setting')
            payload['output_config'] = {'effort': effort}
        if thinking is not None:
            if thinking not in ('adaptive','disabled'):
                raise ValueError('Supported thinking settings are adaptive and disabled')
            if thinking == 'disabled' and effort in ('xhigh','max'):
                raise ValueError('High effort requires thinking on this configuration')
            payload['thinking'] = {'type': thinking}
        return payload
    if provider in {'deepinfra','openai'}:
        if effort is not None or thinking is not None:
            raise ValueError('Anthropic reasoning settings cannot be sent to this provider')
        payload={'model':model,'messages':[{'role':'system','content':system},{'role':'user','content':user}], 'max_tokens':max_output_tokens}
        if temperature is not None: payload['temperature']=temperature
        return payload
    raise ValueError('Unknown provider: '+provider)

DEFAULT_TIMEOUT_SECONDS = 300


def invoke(provider,payload,timeout=DEFAULT_TIMEOUT_SECONDS):
    if not isinstance(timeout,(int,float)) or not 0 < timeout < float("inf"):
        raise ValueError("Request timeout must be a positive finite number")
    if provider=='anthropic':
        api_key=os.environ.get('ANTHROPIC_API_KEY')
        if not api_key: raise ProviderError('ANTHROPIC_API_KEY is not set; no request sent')
        url='https://api.anthropic.com/v1/messages'
        headers={'x-api-key':api_key,'anthropic-version':'2023-06-01'}
    elif provider in {'deepinfra','openai'}:
        env='DEEPINFRA_API_KEY' if provider=='deepinfra' else 'OPENAI_API_KEY'
        api_key=os.environ.get(env)
        if not api_key: raise ProviderError(env+' is not set; no request sent')
        url='https://api.deepinfra.com/v1/openai/chat/completions' if provider=='deepinfra' else 'https://api.openai.com/v1/chat/completions'
        headers={'Authorization':'Bearer '+api_key}
    else:raise ValueError('Unexpected provider')
    headers.update({'Content-Type':'application/json'})
    req=urllib.request.Request(url,data=json.dumps(payload).encode('utf-8'),headers=headers,method='POST')
    start=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=timeout) as f:
            raw=f.read().decode('utf-8'); data=json.loads(raw)
    except urllib.error.HTTPError as e:
        body=e.read().decode('utf-8',errors='replace')[:8000]
        error=ProviderError(f'HTTP {e.code}: {body[:500]}',status=e.code,retryable=e.code in (408,409,429,500,502,503,504),raw=body)
        try:error.retry_after=max(0.,float(e.headers.get('Retry-After','0')))
        except (ValueError,TypeError):pass
        raise error
    except (TimeoutError,urllib.error.URLError,ConnectionError,http.client.IncompleteRead) as e:
        # Unknown whether the provider processed the request: caller must not blindly retry.
        raise ProviderError('AMBIGUOUS_NETWORK_FAILURE: '+str(e),status=None,retryable=False)
    except json.JSONDecodeError as e:
        raise ProviderError('Invalid provider JSON: '+str(e),retryable=False)
    return parse_response(provider,data,time.monotonic()-start)


def parse_response(provider,data,elapsed_seconds=0.0):
    """Normalize live and archived provider responses identically."""
    if provider=='anthropic':
        parts=[p.get('text','') for p in data.get('content',[]) if p.get('type')=='text']
        response='\n'.join(parts)
        usage=data.get('usage') or {}
        inp=usage.get('input_tokens',0)+usage.get('cache_creation_input_tokens',0)+usage.get('cache_read_input_tokens',0)
        out=usage.get('output_tokens',0)
        stop=data.get('stop_reason')
    else:
        choices=data.get('choices') or []
        if not choices:raise ProviderError('No choices in provider response',retryable=False,raw=data)
        msg=choices[0].get('message') or {}
        val=msg.get('content','')
        response=val if isinstance(val,str) else '\n'.join(x.get('text','') for x in val if isinstance(x,dict))
        usage=data.get('usage') or {}
        inp=usage.get('prompt_tokens',0)
        out=usage.get('completion_tokens',0)
        stop=choices[0].get('finish_reason')
    return {'text':response,'raw':data,'served_model':data.get('model'),
            'response_id':data.get('id'),'input_tokens':inp,'output_tokens':out,'stop_reason':stop,
            'elapsed_seconds':round(elapsed_seconds,3)}

def cost_usd(input_tokens,output_tokens,rates):
    if rates.get('input_usd_per_million') is None or rates.get('output_usd_per_million') is None:
        raise ValueError('Set provider input/output rates in config.json before live calls')
    return (input_tokens*rates['input_usd_per_million']+output_tokens*rates['output_usd_per_million'])/1_000_000

def conservative_reservation(payload,rates):
    # Approximate upper-bound reservation, not a provider billing guarantee.
    import json
    # Four chars/token underestimates some code; using two chars/token is intentionally conservative.
    approx_input=(len(json.dumps(payload))+1)//2
    return cost_usd(approx_input,payload.get('max_tokens',0),rates)*1.25
