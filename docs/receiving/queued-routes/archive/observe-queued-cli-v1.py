"""Supported Python audit observer for one actual module invocation."""
import json, os, pathlib, runpy, sys
sys.dont_write_bytecode=True
source,root,log,*arguments=sys.argv[1:]
raw_open,raw_write,raw_close=os.open,os.write,os.close
busy=False
def emit(record):
    global busy
    if busy:return
    busy=True
    try:
        fd=raw_open(log,os.O_WRONLY|os.O_APPEND)
        try:raw_write(fd,(json.dumps(record,ensure_ascii=True)+"\n").encode())
        finally:raw_close(fd)
    finally:busy=False
def audit(event,args):
    if event=="open":
        p=args[0]
        if isinstance(p,(str,bytes)):
            p=os.fsdecode(p)
            if p!=log and (p==root or p.startswith(root+os.sep)):
                emit({"event":event,"path":p,"mode":args[1],"flags":args[2]})
    elif event=="sqlite3.connect":
        emit({"event":event,"database":str(args[0])})
    elif event in ("socket.connect","subprocess.Popen","os.system"):
        emit({"event":event})
sys.addaudithook(audit)
sys.path.insert(0,source)
sys.argv=["fanout_engine.queued_routes",*arguments]
runpy.run_module("fanout_engine.queued_routes",run_name="__main__")
