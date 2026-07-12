#!/usr/bin/env python3
"""Serve an HTML artifact with annotations and agent feedback."""

from __future__ import annotations

import argparse
import html
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, TypeAlias

JsonObject: TypeAlias = dict[str, Any]

_SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HTML Review</title><style>
:root{color-scheme:light dark;--bg:#f4f5f7;--panel:#fff;--text:#181a1f;--muted:#69707d;--line:#dfe2e7;--accent:#3157d5;--soft:#eef1f6}
@media(prefers-color-scheme:dark){:root{--bg:#101217;--panel:#191c22;--text:#f1f3f7;--muted:#a7adba;--line:#303641;--accent:#8ca4ff;--soft:#22262e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 ui-sans-serif,system-ui,sans-serif}.bar{height:52px;display:flex;align-items:center;gap:14px;padding:0 16px;border-bottom:1px solid var(--line);background:var(--panel)}.brand{font-weight:750}.hint{color:var(--muted);font-size:12px}.spacer{flex:1}.toggle,.send{border:1px solid var(--line);border-radius:9px;background:var(--soft);color:var(--text);padding:8px 11px;font:inherit;font-weight:650;cursor:pointer}.toggle[aria-pressed=true],.send{border-color:var(--accent);background:var(--accent);color:#fff}.layout{height:calc(100vh - 52px);display:grid;grid-template-columns:minmax(0,1fr) 320px}.frame{min-width:0;background:var(--panel)}iframe{width:100%;height:100%;border:0;background:white}.panel{min-width:0;display:flex;flex-direction:column;border-left:1px solid var(--line);background:var(--panel)}.panel h2{margin:0;padding:18px 16px 8px;font-size:14px}.queue{flex:1;overflow:auto;padding:8px 12px;display:grid;align-content:start;gap:8px}.empty{padding:10px 4px;color:var(--muted)}.item{position:relative;padding:11px 34px 11px 12px;border:1px solid var(--line);border-radius:10px;background:var(--soft);overflow-wrap:anywhere}.item small{display:block;color:var(--muted);margin-bottom:3px}.remove{position:absolute;right:6px;top:6px;border:0;background:transparent;color:var(--muted);font-size:18px;cursor:pointer}.composer{padding:12px;border-top:1px solid var(--line)}textarea{width:100%;min-height:76px;resize:vertical;border:1px solid var(--line);border-radius:9px;background:var(--bg);color:var(--text);padding:9px;font:inherit}.actions{display:flex;justify-content:flex-end;margin-top:8px}.status{min-height:18px;margin-top:6px;color:var(--muted);font-size:12px}@media(max-width:760px){.layout{grid-template-columns:1fr;grid-template-rows:minmax(55vh,1fr) auto;height:auto;min-height:calc(100vh - 52px)}.frame{height:60vh}.panel{border-left:0;border-top:1px solid var(--line)}.queue{max-height:220px}}
</style></head><body><header class="bar"><span class="brand">HTML Review</span><span class="hint">⌘↵ queue · ⌘S send</span><span class="spacer"></span><button class="toggle" id="annotate" aria-pressed="true">Annotate</button></header><div class="layout"><div class="frame"><iframe id="artifact" src="/artifact"></iframe></div><aside class="panel"><h2>Feedback</h2><div class="queue" id="queue"><div class="empty">Answers and annotations will appear here.</div></div><div class="composer"><textarea id="message" placeholder="Add a general note…"></textarea><div class="actions"><button class="send" id="send" title="Send to agent (⌘S / Ctrl+S)">Send to agent</button></div><div class="status" id="status"></div></div></aside></div><script>
const frame=document.querySelector('#artifact'),queueEl=document.querySelector('#queue'),message=document.querySelector('#message'),status=document.querySelector('#status');let queue=[],mtime=0,annotate=true;
function render(){queueEl.innerHTML=queue.length?'':'<div class="empty">Answers and annotations will appear here.</div>';queue.forEach((item,i)=>{const el=document.createElement('div');el.className='item';el.innerHTML=`<small>${escapeHtml(item.tag||'feedback')}</small>${escapeHtml(item.text||item.prompt)}<button class="remove" aria-label="Remove">×</button>`;el.querySelector('button').onclick=()=>{queue.splice(i,1);render()};queueEl.append(el)})}
function escapeHtml(value){const el=document.createElement('span');el.textContent=value;return el.innerHTML}
window.addEventListener('message',event=>{if(event.source!==frame.contentWindow||event.data?.type!=='html-review:queue')return;const item=event.data.item,key=item.queueKey;if(key){const index=queue.findIndex(value=>value.queueKey===key);index<0?queue.push(item):queue.splice(index,1,item)}else queue.push(item);render()});
document.querySelector('#annotate').onclick=event=>{annotate=!annotate;event.currentTarget.setAttribute('aria-pressed',String(annotate));frame.contentWindow.postMessage({type:'html-review:annotate',enabled:annotate},'*')};
function queueMessage(){const note=message.value.trim();if(!note)return false;queue.push({tag:'message',text:note,prompt:note});message.value='';render();status.textContent='Message queued.';return true}
async function sendFeedback(){const note=message.value.trim();const items=note?[...queue,{tag:'message',text:note,prompt:note}]:queue;if(!items.length){status.textContent='Add feedback first.';return}const response=await fetch('/api/feedback',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({items})});if(!response.ok){status.textContent='Could not send feedback.';return}queue=[];message.value='';render();status.textContent='Sent to agent.'}
document.querySelector('#send').onclick=sendFeedback;
document.addEventListener('keydown',event=>{if(!(event.metaKey||event.ctrlKey))return;if(event.key==='s'){event.preventDefault();sendFeedback()}else if(event.key==='Enter'&&document.activeElement===message){event.preventDefault();queueMessage()}});
window.addEventListener('message',event=>{if(event.source===frame.contentWindow&&event.data?.type==='html-review:send'){sendFeedback()}});
async function watch(){try{const data=await fetch('/api/meta').then(r=>r.json());if(mtime&&data.mtime!==mtime)frame.contentWindow.location.reload();mtime=data.mtime}catch{}setTimeout(watch,1000)}watch();
</script></body></html>"""

_SDK = r"""(() => {
  let enabled = true, card, selected;
  const interactive = "button,input,select,textarea,label,option,a,summary,[contenteditable=true],[data-review-action],[data-review-ui]";
  function annotationTarget(target){return target instanceof Element&&!target.closest(interactive)&&!target.matches('html,body,main,[data-review-ignore]')?target:null}
  function cssPath(el) { const parts=[]; while(el&&el.nodeType===1&&el!==document.body){let part=el.tagName.toLowerCase();if(el.id){parts.unshift(part+'#'+CSS.escape(el.id));break}const siblings=[...el.parentElement.children].filter(x=>x.tagName===el.tagName);if(siblings.length>1)part+=`:nth-of-type(${siblings.indexOf(el)+1})`;parts.unshift(part);el=el.parentElement}return parts.join(' > ')||'body' }
  function queuePrompt(prompt, options={}) { const element=options.element,queueKey=options.queueKey===undefined?(element?.closest('[data-review-question]')?.dataset.reviewQuestion||''):options.queueKey; parent.postMessage({type:'html-review:queue',item:{prompt,text:options.text||prompt,tag:options.tag||'answer',data:options.data||{},selector:options.selector||(element?cssPath(element):''),queueKey}},'*') }
  window.htmlReview={queuePrompt};
  const style=document.createElement('style');style.dataset.reviewUi='';style.textContent='[data-review-hover]{outline:2px solid #6685ff!important;outline-offset:2px!important}[data-review-selected]{outline:2px solid #3157d5!important;outline-offset:3px!important}.html-review-highlight{background:#ffe87880}.html-review-card{position:fixed;z-index:2147483647;width:min(320px,calc(100vw - 24px));padding:12px;border:1px solid #6685ff;border-radius:12px;background:#171a21;color:#f4f5f7;box-shadow:0 18px 60px #0007;font:14px/1.4 ui-sans-serif,system-ui,sans-serif}.html-review-card textarea{box-sizing:border-box;width:100%;min-height:76px;margin:8px 0;border:1px solid #3d4554;border-radius:8px;background:#0f1115;color:#fff;padding:8px;font:inherit}.html-review-card button{border:0;border-radius:8px;padding:7px 10px;font:inherit;font-weight:700;cursor:pointer}.html-review-card .row{display:flex;justify-content:flex-end;gap:7px}.html-review-card .cancel{background:#303745;color:#fff}.html-review-card .queue{background:#8ca4ff;color:#101217}';document.head.append(style);
  function close(){card?.remove();card=null;selected?.removeAttribute('data-review-selected');selected=null;document.querySelectorAll('.html-review-highlight').forEach(el=>el.classList.remove('html-review-highlight'))}
  function openCard(target, selection){close();selected=target;target.setAttribute('data-review-selected','');if(selection)selection.classList.add('html-review-highlight');card=document.createElement('div');card.dataset.reviewUi='';card.className='html-review-card';card.innerHTML=`<strong>Annotate ${selection?'selected text':'this element'}</strong><textarea placeholder="What should change?"></textarea><div class="row"><button class="cancel">Cancel</button><button class="queue" title="Queue (⌘Enter / Ctrl+Enter)">Queue</button></div>`;document.body.append(card);const rect=target.getBoundingClientRect();card.style.left=Math.max(12,Math.min(innerWidth-332,rect.left))+'px';card.style.top=Math.max(12,Math.min(innerHeight-card.offsetHeight-12,rect.bottom+8))+'px';card.querySelector('.cancel').onclick=close;card.querySelector('.queue').onclick=()=>{const prompt=card.querySelector('textarea').value.trim();if(!prompt)return;queuePrompt(prompt,{tag:'annotation',text:prompt,element:target,queueKey:'',data:selection?{selectedText:selection.textContent}: {}});close()};card.querySelector('textarea').focus()}
  document.addEventListener('mouseover',event=>{const target=annotationTarget(event.target);if(enabled&&target)target.setAttribute('data-review-hover','')});document.addEventListener('mouseout',event=>event.target.removeAttribute?.('data-review-hover'));
  document.addEventListener('click',event=>{const target=annotationTarget(event.target);if(!enabled||!target)return;event.preventDefault();event.stopPropagation();const range=window.getSelection();if(range&&!range.isCollapsed&&range.toString().trim()){const span=document.createElement('span');span.textContent=range.toString();try{range.getRangeAt(0).surroundContents(span);openCard(span,span)}catch{openCard(target)}range.removeAllRanges()}else openCard(target)},true);
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&card){event.preventDefault();close();return}if(!(event.metaKey||event.ctrlKey))return;if(event.key==='s'){event.preventDefault();parent.postMessage({type:'html-review:send'},'*')}else if(event.key==='Enter'){const form=event.target.closest?.('form[data-review-question]');if(card&&card.contains(event.target)){event.preventDefault();card.querySelector('.queue').click()}else if(form){event.preventDefault();form.requestSubmit()}}});
  addEventListener('message',event=>{if(event.data?.type==='html-review:annotate'){enabled=!!event.data.enabled;if(!enabled)close()}});
})();"""


def _state_path(artifact: Path) -> Path:
    return artifact.parent / f".{artifact.stem}.html-review.json"


def _read_json(path: Path) -> JsonObject:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, value: JsonObject) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def _artifact_html(artifact: Path) -> bytes:
    content = artifact.read_text()
    injection = '<script src="/sdk.js"></script>'
    return (
        content.replace("</body>", f"{injection}</body>", 1)
        if "</body>" in content
        else content + injection
    ).encode()


def _handler(artifact: Path, state_path: Path) -> type[BaseHTTPRequestHandler]:
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def _send(
            self, content: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self) -> None:
            path = urllib.parse.urlparse(self.path).path
            if path == "/":
                self._send(_SHELL.encode(), "text/html; charset=utf-8")
            elif path == "/artifact":
                self._send(_artifact_html(artifact), "text/html; charset=utf-8")
            elif path == "/sdk.js":
                self._send(_SDK.encode(), "text/javascript; charset=utf-8")
            elif path == "/api/meta":
                self._send(
                    json.dumps({"mtime": artifact.stat().st_mtime_ns}).encode(),
                    "application/json",
                )
            else:
                self._send(b"Not found", "text/plain", HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if urllib.parse.urlparse(self.path).path != "/api/feedback":
                self._send(b"Not found", "text/plain", HTTPStatus.NOT_FOUND)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size > 1_000_000:
                    raise ValueError("feedback exceeds 1 MB")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload.get("items"), list) or not payload["items"]:
                    raise ValueError("items must be a non-empty list")
            except (ValueError, json.JSONDecodeError) as error:
                self._send(str(error).encode(), "text/plain", HTTPStatus.BAD_REQUEST)
                return
            with lock:
                state = _read_json(state_path)
                state.setdefault("feedback", []).append(
                    {"created": time.time(), "items": payload["items"]}
                )
                _write_json(state_path, state)
            self._send(b'{"ok":true}', "application/json")

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def _serve(args: argparse.Namespace) -> None:
    artifact, state_path = Path(args.file).resolve(), Path(args.state).resolve()
    server = ThreadingHTTPServer((args.host, args.port), _handler(artifact, state_path))
    state = _read_json(state_path) | {
        "artifact": str(artifact),
        "host": args.host,
        "port": server.server_port,
        "pid": os.getpid(),
        "feedback": _read_json(state_path).get("feedback", []),
    }
    _write_json(state_path, state)
    server.serve_forever()


def _open(args: argparse.Namespace) -> None:
    artifact = Path(args.file).resolve()
    if not artifact.is_file():
        raise SystemExit(f"HTML file not found: {artifact}")
    state_path = _state_path(artifact)
    state = _read_json(state_path)
    if pid := state.get("pid"):
        try:
            os.kill(pid, 0)
        except OSError:
            state = {}
    if not state:
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "_serve",
            str(artifact),
            str(state_path),
            "--host",
            args.host,
            "--port",
            str(args.port),
        ]
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        for _ in range(50):
            if (state := _read_json(state_path)).get("port"):
                break
            time.sleep(0.1)
        else:
            raise SystemExit("Review server did not start")
    link_host = args.link_host or (
        "127.0.0.1" if state["host"] in {"0.0.0.0", "::"} else state["host"]
    )
    url = f"http://{link_host}:{state['port']}"
    print(url)
    if not args.no_open:
        webbrowser.open(url)


def _poll(args: argparse.Namespace) -> None:
    state_path = _state_path(Path(args.file).resolve())
    deadline = time.monotonic() + args.timeout if args.timeout else None
    while True:
        state = _read_json(state_path)
        if feedback := state.get("feedback"):
            print(json.dumps({"status": "feedback", "batches": feedback}, indent=2))
            state["feedback"] = []
            _write_json(state_path, state)
            return
        if deadline and time.monotonic() >= deadline:
            print(json.dumps({"status": "timeout"}))
            return
        time.sleep(0.25)


def _end(args: argparse.Namespace) -> None:
    state_path = _state_path(Path(args.file).resolve())
    state = _read_json(state_path)
    if pid := state.get("pid"):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    state_path.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    open_parser = subparsers.add_parser("open", help="start a review session")
    open_parser.add_argument("file")
    open_parser.add_argument("--host", default="127.0.0.1")
    open_parser.add_argument("--port", type=int, default=0)
    open_parser.add_argument("--link-host")
    open_parser.add_argument("--no-open", action="store_true")
    open_parser.set_defaults(run=_open)
    poll_parser = subparsers.add_parser("poll", help="wait for feedback")
    poll_parser.add_argument("file")
    poll_parser.add_argument("--timeout", type=float, default=0)
    poll_parser.set_defaults(run=_poll)
    end_parser = subparsers.add_parser("end", help="end a review session")
    end_parser.add_argument("file")
    end_parser.set_defaults(run=_end)
    serve_parser = subparsers.add_parser("_serve", help=argparse.SUPPRESS)
    serve_parser.add_argument("file")
    serve_parser.add_argument("state")
    serve_parser.add_argument("--host", required=True)
    serve_parser.add_argument("--port", type=int, required=True)
    serve_parser.set_defaults(run=_serve)
    return parser


if __name__ == "__main__":
    parsed = _parser().parse_args()
    parsed.run(parsed)
