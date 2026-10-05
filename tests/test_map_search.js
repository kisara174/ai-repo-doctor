const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// A small DOM surface executes the shipped viewer and its actual event handlers.
class Element {
  constructor(name) { this.name=name; this.children=[]; this.style={}; this.attributes={}; this.value=''; this._text=''; }
  set textContent(value) { this._text=String(value); this.children=[]; }
  get textContent() { return this._text+this.children.map(child=>child.textContent).join(''); }
  appendChild(child) { if(child.name==='#fragment') this.children.push(...child.children); else this.children.push(child); return child; }
  append(...children) { children.forEach(child=>this.appendChild(child)); }
  replaceChildren(...children) { this.children=[]; this._text=''; this.append(...children); }
  setAttribute(name,value) { this.attributes[name]=String(value); }
  addEventListener() {}
  getBoundingClientRect() { return {width:960,height:600}; }
  querySelectorAll(name) { return this.children.flatMap(child=>[...(child.name===name?[child]:[]),...child.querySelectorAll(name)]); }
}
const node=(id,kind,file,parent,label,start_line,is_test=false)=>({id,kind,file,parent,label,start_line,is_test,python:kind==='file'});
for (const capped of [false, true]) {
const data={
  nodes:[node('dir:.','directory','.',null,'repo'), node('dir:pkg','directory','pkg','dir:.','pkg'),
    node('file:pkg/a.py','file','pkg/a.py','dir:pkg','a.py'),
    node('symbol:pkg/a.py::C','class','pkg/a.py','file:pkg/a.py','C',3),
    node('symbol:pkg/a.py::C.run','method','pkg/a.py','symbol:pkg/a.py::C','run',7),
    node('file:b.py','file','b.py','dir:.','b.py'), node('symbol:b.py::run','function','b.py','file:b.py','run',11),
    node('file:test_a.py','file','test_a.py','dir:.','test_a.py',null,true),
    node('symbol:test_a.py::run','function','test_a.py','file:test_a.py','run',5,true)],
  edges:[],file_edges:[{id:'fcall',kind:'call',source:'file:b.py',target:'file:pkg/a.py'}],
  initial:{symbol:null,depth:1},limits:{nodes:200,edges:500},
  layout:{margin:30,header:120,indent:26,node_width:260,node_height:54,column_gap:320,row_gap:90,columns:3},
  colors:{contains:'#aaa',call:'#00f',import:'#0a0',reexport:'#f00',command_registration:'#ff0'},
  repository:{name:'fixture',source_fingerprint:'0'.repeat(64),revision:'fixture'},coverage:{unresolved_calls:0,parse_errors:0},
};
if(capped) for(let i=0;i<220;i++) {
  const file='a'+String(i).padStart(3,'0')+'.py';
  data.nodes.push(node('file:'+file,'file',file,'dir:.',file));
}
for(const n of data.nodes.filter(n=>n.parent)) data.edges.push({id:'contains:'+n.id,kind:'contains',source:n.parent,target:n.id});
data.edges.push({id:'call',kind:'call',source:'symbol:b.py::run',target:'symbol:pkg/a.py::C.run'});
const elements=new Map();
const document={getElementById(id){if(!elements.has(id))elements.set(id,new Element(id));return elements.get(id);},
  createElement:name=>new Element(name),createElementNS:(_,name)=>new Element(name),
  createDocumentFragment:()=>new Element('#fragment'),createTextNode:text=>{const n=new Element('#text');n.textContent=text;return n;}};
document.getElementById('map-data').textContent=JSON.stringify(data);
const scope={document};
const viewer=process.argv[2]||path.join(__dirname,'../repo_doctor/resources/map/viewer.js');
vm.runInNewContext(fs.readFileSync(viewer,'utf8'),scope);
const $=id=>document.getElementById(id);
const choices=()=>$('node-list').querySelectorAll('button').filter(button=>button.className==='choose');
const search=value=>{$('search').value=value;$('search').oninput();return choices();};
if(process.env.MAP_TEST_SECTION!=='counts') {
  assert.equal(search('run').length,2,'Label search retains duplicate non-test names');
  for(const query of ['pkg/a.py::C.run','symbol:pkg/a.py::C.run',' SYMBOL:PKG/A.PY::C.RUN ']) {
    const matches=search(query);
    assert.equal(matches.length,1,'Full ID search must identify a symbol: '+query);
    assert.equal(matches[0].title,'pkg/a.py');
  }
  choices()[0].onclick();
  assert.equal($('selection').textContent,'run\npkg/a.py:7','Selection must preserve physical source line');
  $('search').value='';$('mode').value='structure';$('mode').onchange();
  const drawn=$('drawing').children[0].children.filter(n=>n.attributes['data-node-id']).map(n=>n.attributes['data-node-id']);
  assert.ok(drawn.length<=200,'Selection must retain the configured node cap');
  if(capped) assert.equal(drawn.length,200,'Large fixture must exercise truncation');
  for(const id of ['dir:pkg','file:pkg/a.py','symbol:pkg/a.py::C','symbol:pkg/a.py::C.run']) assert.ok(drawn.includes(id),'Search must reveal ancestor path: '+id);
  assert.equal(search('symbol:test_a.py::run').length,0,'Tests remain excluded by default');
  $('tests').checked=true;$('tests').onchange();
  assert.equal(search('symbol:test_a.py::run').length,1,'Explicit test filter enables ID search');
  console.log('Map search: full/prefixed ID, duplicate names, source lines, ancestors and test filtering passed');
}
if(!capped && process.env.MAP_TEST_SECTION!=='search') {
  $('reset').onclick();$('tests').checked=false;$('tests').onchange();
  assert.match($('summary').textContent,/6 个节点未显示/);
  assert.match($('summary').textContent,/6 条连线未显示/,'HTML status must expose hidden structure edges');
  $('mode').value='relations';$('mode').onchange();
  assert.match($('summary').textContent,/7 个节点未显示/);
  assert.match($('summary').textContent,/0 条连线未显示/,'HTML status must expose hidden relation edges');
  console.log('Map status: hidden node and edge counts follow the active projection');
}
}
