const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const scope = {};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../repo_doctor/resources/map/viewer.js'), 'utf8'), scope);
const data = {
  nodes: [
    {id:'dir:.',kind:'directory',file:'.',parent:null,is_test:false},
    {id:'file:a.py',kind:'file',file:'a.py',parent:'dir:.',is_test:false,python:true},
    {id:'symbol:a.py::C',kind:'class',file:'a.py',parent:'file:a.py',is_test:false,start_line:1},
    {id:'symbol:a.py::C.run',kind:'method',file:'a.py',parent:'symbol:a.py::C',is_test:false,start_line:2},
    {id:'file:test_a.py',kind:'file',file:'test_a.py',parent:'dir:.',is_test:true,python:true},
  ],
  edges: [
    {id:'c1',kind:'contains',source:'dir:.',target:'file:a.py'},
    {id:'c2',kind:'contains',source:'file:a.py',target:'symbol:a.py::C'},
    {id:'c3',kind:'contains',source:'symbol:a.py::C',target:'symbol:a.py::C.run'},
  ], file_edges:[], limits:{nodes:200,edges:500},
  layout:{margin:30,header:120,indent:26,node_width:260,node_height:54,column_gap:320,row_gap:90,columns:3},
};
const state={mode:'structure',tests:false,kinds:[],expanded:['symbol:a.py::C'],closed:[]};
const ids=view=>Array.from(view.nodes,n=>n.id);
assert.deepEqual(ids(scope.RepoMap.project(data,state)),['dir:.','file:a.py'], 'A collapsed file must hide all descendants');
state.expanded=['file:a.py','symbol:a.py::C'];
assert.deepEqual(ids(scope.RepoMap.project(data,state)),['dir:.','file:a.py','symbol:a.py::C','symbol:a.py::C.run'], 'Expanded parents must precede their methods');
const view=scope.RepoMap.project(data,{mode:'relations',tests:false,kinds:[],target:null,depth:1});
assert.deepEqual(ids(view),['file:a.py'], 'Default graph must hide test files');
data.nodes.push(
  {id:'file:b.py',kind:'file',file:'b.py',parent:'dir:.',is_test:false,python:true},
  {id:'symbol:b.py::run',kind:'function',file:'b.py',parent:'file:b.py',is_test:false,start_line:1},
);
data.edges.push({id:'call1',kind:'call',source:'symbol:b.py::run',target:'symbol:a.py::C.run'});
data.file_edges.push({id:'file-call1',kind:'call',source:'file:b.py',target:'file:a.py'});
const fileFocus=scope.RepoMap.project(data,{mode:'relations',tests:false,kinds:['call'],target:'file:a.py',depth:1});
assert.deepEqual(ids(fileFocus),['file:a.py','file:b.py'], 'Selecting a file must retain its calling file');
assert.deepEqual(Array.from(fileFocus.edges,e=>e.id),['file-call1'], 'File focus must retain the aggregated call edge');
const symbolFocus=scope.RepoMap.project(data,{mode:'relations',tests:false,kinds:['call'],target:'symbol:a.py::C.run',depth:1});
assert.deepEqual(Array.from(symbolFocus.edges,e=>e.id),['call1'], 'Symbol focus must retain the actual symbol call');
assert.equal(typeof scope.RepoMap.reveal, 'function', 'Directory search must expose the reveal operation');
data.nodes.push(
  {id:'dir:pkg',kind:'directory',file:'pkg',parent:'dir:.',is_test:false},
  {id:'dir:pkg/deep',kind:'directory',file:'pkg/deep',parent:'dir:pkg',is_test:false},
  {id:'file:pkg/deep/README.md',kind:'file',file:'pkg/deep/README.md',parent:'dir:pkg/deep',is_test:false,python:false},
  {id:'dir:other',kind:'directory',file:'other',parent:'dir:.',is_test:false},
  {id:'file:other/README.md',kind:'file',file:'other/README.md',parent:'dir:other',is_test:false,python:false},
);
data.edges.push(
  {id:'c4',kind:'contains',source:'dir:.',target:'dir:pkg'},
  {id:'c5',kind:'contains',source:'dir:pkg',target:'dir:pkg/deep'},
  {id:'c6',kind:'contains',source:'dir:pkg/deep',target:'file:pkg/deep/README.md'},
  {id:'c7',kind:'contains',source:'dir:.',target:'dir:other'},
  {id:'c8',kind:'contains',source:'dir:other',target:'file:other/README.md'},
);
const revealed=scope.RepoMap.reveal(data,{
  mode:'relations',target:'symbol:a.py::C.run',tests:false,kinds:[],
  closed:['dir:pkg','dir:pkg/deep'],expanded:['file:a.py'],
},'dir:pkg/deep');
assert.equal(revealed.mode,'structure');
assert.equal(revealed.target,null);
assert.equal(revealed.selected,'dir:pkg/deep');
assert.deepEqual(Array.from(revealed.expanded),[],'Directory search must collapse unrelated symbols');
assert.ok(revealed.closed.includes('dir:other'),'Unrelated directory must stay closed');
assert.ok(!revealed.closed.includes('dir:pkg')&&!revealed.closed.includes('dir:pkg/deep'),'Selected directory and ancestors must open');
const revealedView=scope.RepoMap.project(data,revealed);
assert.ok(ids(revealedView).includes('dir:pkg/deep'),'Selected directory must remain visible');
assert.ok(ids(revealedView).includes('file:pkg/deep/README.md'),'Selected directory children must be visible');
assert.ok(!ids(revealedView).includes('file:other/README.md'),'Unrelated directory children must remain hidden');
for(let i=0;i<250;i++) data.nodes.push({
  id:'file:000-'+String(i).padStart(3,'0')+'.md',kind:'file',
  file:'000-'+String(i).padStart(3,'0')+'.md',parent:'dir:.',is_test:false,python:false,
});
const crowded=scope.RepoMap.project(data,revealed);
assert.ok(crowded.nodes.length<=200,'Directory reveal must respect the existing node cap');
for(const required of ['dir:.','dir:pkg','dir:pkg/deep','file:pkg/deep/README.md']) {
  assert.ok(ids(crowded).includes(required),'Directory search must retain '+required+' despite many earlier siblings');
}
const crowdedIds=new Set(ids(crowded));
assert.ok(crowded.edges.every(edge=>crowdedIds.has(edge.source)&&crowdedIds.has(edge.target)),'Capped views must not contain dangling edges');
console.log('Map viewer: collapsed descendants, hierarchy order, test filtering, and file/symbol call focus passed');
