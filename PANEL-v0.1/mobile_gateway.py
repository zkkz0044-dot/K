#!/usr/bin/python3
from __future__ import annotations
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from panel_server import LocalHTTPServer, Handler as LocalHandler

UPSTREAM_HOST='127.0.0.1'
UPSTREAM_PORT=8877
MAX_BODY=64_000_000

class Handler(LocalHandler):
    server_version='KMobileGateway/1.1'
    def log_message(self,_fmt,*_args):
        return
    def proxy(self):
        try:
            n=int(self.headers.get('Content-Length','0') or '0')
        except ValueError:
            n=0
        if n<0 or n>MAX_BODY:
            self.send_error(413); return
        body=self.rfile.read(n) if n else None
        headers={}
        ctype=self.headers.get('Content-Type')
        if ctype: headers['Content-Type']=ctype
        conn=http.client.HTTPConnection(UPSTREAM_HOST,UPSTREAM_PORT,timeout=160)
        try:
            conn.request(self.command,self.path,body=body,headers=headers)
            res=conn.getresponse(); data=res.read()
            self.send_response(res.status)
            for k,v in res.getheaders():
                if k.lower() not in {'connection','transfer-encoding','server','date','content-length'}:
                    self.send_header(k,v)
            self.send_header('Content-Length',str(len(data)))
            self.end_headers(); self.wfile.write(data)
        except Exception:
            self.send_error(502)
        finally:
            conn.close()
    def do_GET(self):
        if self.local_request(): self.proxy()
    def do_POST(self):
        if self.local_request(): self.proxy()

if __name__=='__main__':
    LocalHTTPServer(('127.0.0.1',8878),Handler).serve_forever()
