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
console.log('Map viewer: collapsed descendants, hierarchy order, test filtering, and file/symbol call focus passed');
