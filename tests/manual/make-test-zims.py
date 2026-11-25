import sys
from pathlib import Path
from libzim.writer import Creator, Item, StringProvider, Hint

out = Path(sys.argv[1])

class Page(Item):
    def __init__(s, path, title, html): super().__init__(); s.p, s.t, s.h = path, title, html
    def get_path(s): return s.p
    def get_title(s): return s.t
    def get_mimetype(s): return "text/html"
    def get_contentprovider(s): return StringProvider(s.h)
    def get_hints(s): return {Hint.FRONT_ARTICLE: True}

SHELL = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>shell</title>
<style>body{margin:0;font-family:sans-serif}#bar{background:#1a5fb4;color:#fff;padding:8px}#f{width:100%;height:80vh;border:0}</style></head>
<body><div id="bar">ARC BAR <span id="where"></span></div><pre id="log"></pre><iframe id="f"></iframe>
<script>
var L=[];function log(k,v){L.push(k+'='+v);document.getElementById('log').textContent=L.join('\n');document.title='RESULT '+L.join(' | ');}
log('script','runs');
var f=document.getElementById('f');
var target=location.hash.slice(1)||'noindex/a.html';
f.onload=function(){
  try{var d=f.contentWindow.document;log('frame_read','ok:'+d.title+' @ '+f.contentWindow.location.pathname);}
  catch(e){log('frame_read','blocked:'+e.name);}
};
f.src='/content/'+target;
fetch('/search?format=xml&books.name=wikipedia_en_100_mini_2025-06&books.name=arcspike&pattern=water&pageLength=5').then(function(r){return r.text()}).then(function(t){log('search_xml',(t.match(/<item>/g)||[]).length+' items, starts '+JSON.stringify(t.slice(0,60)))}).catch(function(e){log('search_xml','fail '+e)});
fetch('/suggest?content=noindex&term=Bic').then(function(r){return r.text()}).then(function(t){log('suggest_noindex',t.slice(0,200))}).catch(function(e){log('suggest_noindex','fail '+e)});
</script></body></html>"""

def make(name, pages, index):
    tmp = out / f"{name}.zim"
    with Creator(str(tmp)).config_indexing(index, "eng") as c:
        c.set_mainpath("index.html")
        for k, v in {"Name": name, "Title": name, "Description": "spike", "Language": "eng",
                     "Creator": "spike", "Publisher": "spike", "Date": "2026-11-25"}.items():
            c.add_metadata(k, v)
        for p in pages: c.add_item(Page(*p))

make("arcspike", [("index.html", "Arc home", "<html><body><h1>Arc home</h1><p>Clean water guide test.</p></body></html>"),
                  ("shell.html", "Shell", SHELL)], True)
make("noindex", [("index.html", "Noindex home", "<html><head><title>Noindex home</title></head><body><a href='a.html'>a</a></body></html>"),
                 ("a.html", "Bicycle chain repair", "<html><head><title>Bicycle chain repair</title></head><body><h1>Bicycle chain</h1><a href='b.html'>next page</a></body></html>"),
                 ("b.html", "Bicycle brakes", "<html><head><title>Bicycle brakes</title></head><body><h1>Brakes</h1></body></html>")], False)
print("ok")
