/* Offline SVG viewer. No source execution, network or external resources. */
(() => {
  'use strict';
  const kinds = ['import', 'call', 'reexport', 'command_registration'];
  const labels = {contains:'包含', import:'导入', call:'调用', reexport:'重导出', command_registration:'注册'};
  function reveal(data, state, nodeId) {
    const lookup=new Map(data.nodes.map(n=>[n.id,n]));
    if(!lookup.has(nodeId))return state;
    const open=new Set(), expanded=[];
    for(let id=nodeId;lookup.has(id);id=lookup.get(id).parent){
      const node=lookup.get(id);
      if(node.kind==='directory')open.add(id);else expanded.push(id);
    }
    return {...state,mode:'structure',target:null,selected:nodeId,expanded,
      closed:data.nodes.filter(n=>n.kind==='directory'&&!open.has(n.id)).map(n=>n.id)};
  }
  function structureOrder(a,b) {
    const x=a.id==='dir:.'?'':a.file, y=b.id==='dir:.'?'':b.file;
    return x<y?-1:x>y?1:(a.start_line||-1)-(b.start_line||-1)||(a.id<b.id?-1:a.id>b.id?1:0);
  }
  function position(data, view) {
    const l = data.layout, lookup = new Map(data.nodes.map(n => [n.id,n]));
    const nodes = view.nodes.map((n,i) => {
      let level=0, parent=n.parent;
      while(lookup.has(parent)) { level++; parent=lookup.get(parent).parent; }
      return {...n, x:l.margin+(view.mode==='structure'?level*l.indent:(i%l.columns)*l.column_gap),
        y:l.header+(view.mode==='structure'?i:Math.floor(i/l.columns))*l.row_gap};
    });
    return {...view, nodes, width:Math.max(960,...nodes.map(n=>n.x+l.node_width+30)),
      height:Math.max(300,...nodes.map(n=>n.y+l.node_height+30))};
  }
  function project(data, state) {
    let nodes, edges=data.edges;
    if(state.mode==='structure') {
      const closed=new Set(state.closed||[]), lookup=new Map(data.nodes.map(n=>[n.id,n]));
      const expanded=new Set(state.expanded||[]);
      nodes=data.nodes.filter(n=>{let p=n.parent;while(lookup.has(p)){const parent=lookup.get(p);
        if(parent.kind==='directory'?closed.has(p):!expanded.has(p))return false;p=parent.parent;}return true;});
      nodes.sort(structureOrder);
      edges=edges.filter(e=>e.kind==='contains');
    } else if(state.target) {
      edges=state.target.startsWith('file:')?data.file_edges:edges.filter(e=>e.kind!=='contains');
      const seen=new Set([state.target]), queue=[[state.target,0]];
      while(queue.length){const [current,d]=queue.shift();if(d>=state.depth)continue;
        for(const e of edges){const neighbor=e.source===current?e.target:e.target===current?e.source:null;
          if(neighbor&&!seen.has(neighbor)){seen.add(neighbor);queue.push([neighbor,d+1]);}}
      }
      nodes=data.nodes.filter(n=>seen.has(n.id));
      nodes.sort((a,b)=>a.id===state.target?-1:b.id===state.target?1:a.id<b.id?-1:a.id>b.id?1:0);
    } else {
      nodes=data.nodes.filter(n=>n.kind==='file'&&n.python);edges=data.file_edges;
    }
    nodes=nodes.filter(n=>state.tests||!n.is_test||n.id===state.target);
    if(state.mode==='structure'&&state.selected){
      const lookup=new Map(data.nodes.map(n=>[n.id,n])), path=new Set();
      for(let id=state.selected;lookup.has(id);id=lookup.get(id).parent)path.add(id);
      // Reserve the selected path and its children before applying the view cap.
      const priority=n=>path.has(n.id)?0:n.parent===state.selected?1:2;
      nodes.sort((a,b)=>priority(a)-priority(b)||structureOrder(a,b));
    }
    nodes=nodes.slice(0,data.limits.nodes);
    if(state.mode==='structure')nodes.sort(structureOrder);
    const ids=new Set(nodes.map(n=>n.id)), allowed=new Set(state.kinds||kinds);allowed.add('contains');
    const selected=edges.filter(e=>ids.has(e.source)&&ids.has(e.target)&&allowed.has(e.kind)).slice(0,data.limits.edges);
    return position(data,{mode:state.mode,nodes,edges:selected,hidden_nodes:data.nodes.length-nodes.length,hidden_edges:edges.length-selected.length});
  }
  // The pure projection is also exercised without a browser in development.
  globalThis.RepoMap={project,position,reveal};
  if(typeof document==='undefined')return;
  const data=JSON.parse(document.getElementById('map-data').textContent);
  const lookup=new Map(data.nodes.map(n=>[n.id,n]));
  const parents=new Set(data.nodes.map(n=>n.parent));
  const $=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';
  const state={mode:data.initial.symbol?'relations':'structure',target:data.initial.symbol?'symbol:'+data.initial.symbol:null,depth:data.initial.depth,
    tests:false,kinds:[...kinds],selected:null,expanded:[],closed:data.nodes.filter(n=>n.kind==='directory'&&n.id!=='dir:.').map(n=>n.id)};
  let svg, view, camera, dragging;
  function el(parent,name,attrs={},text){const n=document.createElementNS(NS,name);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=String(text);parent.appendChild(n);return n;}
  function text(parent,x,y,size,color,value){return el(parent,'text',{x,y,'font-family':'system-ui, sans-serif','font-size':size,fill:color},value);}
  function render(){
    view=project(data,state);svg=document.createElementNS(NS,'svg');svg.setAttribute('role','img');svg.setAttribute('aria-label','仓库结构关系图');
    el(svg,'title',{},data.repository.name+' · 仓库结构关系图');el(svg,'rect',{width:'100%',height:'100%',fill:'#f8fafc'});
    const defs=el(svg,'defs');
    for(const[kind,color]of Object.entries(data.colors)){const marker=el(defs,'marker',{id:'arrow-'+kind,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});el(marker,'path',{d:'M 0 0 L 10 5 L 0 10 z',fill:color});}
    text(svg,30,32,20,'#0f172a',data.repository.name+' · '+(state.mode==='structure'?'文件结构':'静态关系'));
    text(svg,30,58,12,'#475569',`静态分析 · 未解析调用 ${data.coverage.unresolved_calls} · 解析失败 ${data.coverage.parse_errors} · 未显示节点 ${view.hidden_nodes} / 连线 ${view.hidden_edges}`);
    text(svg,30,80,12,'#64748b',`源码 ${data.repository.source_fingerprint.slice(0,16)} · 修订 ${(data.repository.revision||'无 Git 修订').slice(0,16)} · 箭头：调用者/导入者 → 目标`);
    Object.entries(data.colors).forEach(([k,c],i)=>text(svg,30+i*140,102,12,c,'● '+labels[k]));
    const visible=new Map(view.nodes.map(n=>[n.id,n])), l=data.layout;
    for(const edge of view.edges){const a=visible.get(edge.source),b=visible.get(edge.target);let x1,y1,x2,y2;
      if(b.x>a.x){x1=a.x+l.node_width;y1=a.y+l.node_height/2;x2=b.x;y2=b.y+l.node_height/2;}
      else{x1=a.x+l.node_width/2;y1=a.y+l.node_height;x2=b.x+l.node_width/2;y2=b.y;}
      const geometry=edge.kind==='contains'?`M ${a.x+12} ${a.y+l.node_height} V ${b.y+l.node_height/2} H ${b.x}`:`M ${x1} ${y1} C ${x1+35} ${y1}, ${x2-35} ${y2}, ${x2} ${y2}`;
      const path=el(svg,'path',{d:geometry,fill:'none',stroke:data.colors[edge.kind],'stroke-width':1.5,opacity:.6,'marker-end':`url(#arrow-${edge.kind})`,'data-edge-id':edge.id});
      el(path,'title',{},labels[edge.kind]+': '+a.label+' → '+b.label);
    }
    for(const node of view.nodes){const group=el(svg,'g',{'data-node-id':node.id,transform:`translate(${node.x},${node.y})`,tabindex:0,role:'button','aria-label':node.label});
      el(group,'title',{},node.label+' · '+node.file);el(group,'rect',{width:l.node_width,height:l.node_height,rx:8,fill:node.kind==='directory'?'#eff6ff':'#fff',stroke:node.id===(state.mode==='structure'?state.selected:state.target)?'#2563eb':'#cbd5e1'});
      text(group,12,22,13,'#0f172a',node.label.length<=32?node.label:node.label.slice(0,31)+'…');text(group,12,42,10,'#64748b',node.file.length<=40?node.file:'…'+node.file.slice(-39));
      group.addEventListener('click',()=>select(node));group.addEventListener('keydown',e=>{if(e.key==='Enter')select(node);});
    }
    $('drawing').replaceChildren(svg);fit(state.mode==='structure');
    if(state.mode==='structure'&&state.selected){
      const selected=visible.get(state.selected);
      if(selected){camera.y=Math.max(0,selected.y+l.node_height/2-camera.h/2);applyCamera();}
    }
    list();
    $('summary').textContent=`${view.nodes.length} 个可见节点 · ${view.edges.length} 条连线 · ${view.hidden_nodes} 个节点未显示 · ${view.hidden_edges} 条连线未显示（筛选、层级或上限）`;
  }
  function applyCamera(){svg.setAttribute('viewBox',`${camera.x} ${camera.y} ${camera.w} ${camera.h}`);}
  function fit(widthOnly=false){const box=$('canvas').getBoundingClientRect();camera={x:0,y:0,w:view.width,h:widthOnly?view.width*(box.height||600)/(box.width||960):view.height};applyCamera();}
  function zoom(factor){camera.x+=camera.w*(1-factor)/2;camera.y+=camera.h*(1-factor)/2;camera.w*=factor;camera.h*=factor;applyCamera();}
  function select(node){
    $('selection').textContent=node.label+'\n'+node.file+(node.start_line?':'+node.start_line:'');
    if(state.mode==='relations'&&node.kind!=='directory'){state.target=node.id;state.selected=node.id;}
    if(state.mode==='structure'){state.selected=node.id;if(parents.has(node.id))toggle(node.id);}
    render();
  }
  function toggle(id){const node=lookup.get(id);if(node.kind==='directory'){state.closed=state.closed.includes(id)?state.closed.filter(x=>x!==id):[...state.closed,id];}
    else state.expanded=state.expanded.includes(id)?state.expanded.filter(x=>x!==id):[...state.expanded,id];}
  function list(){
    const query=$('search').value.toLowerCase().trim();let nodes;
    if(query)nodes=data.nodes.filter(n=>(n.label+' '+n.file+' '+n.id).toLowerCase().includes(query)&&(state.tests||!n.is_test));
    else nodes=view.nodes;
    const fragment=document.createDocumentFragment();
    for(const n of nodes.slice(0,100)){const row=document.createElement('div');row.className='node-row';
      if(state.mode==='structure'&&parents.has(n.id)){const button=document.createElement('button');button.className='toggle';button.textContent=n.kind==='directory'?(state.closed.includes(n.id)?'▸':'▾'):(state.expanded.includes(n.id)?'▾':'▸');button.setAttribute('aria-label','展开或收起 '+n.label);button.onclick=()=>{toggle(n.id);render();};row.appendChild(button);}
      const button=document.createElement('button');button.className='choose';button.textContent=n.label;button.title=n.file;button.onclick=()=>{
        if(query){if(n.kind!=='directory'){
          for(let p=n.parent;lookup.has(p);p=lookup.get(p).parent){
            if(lookup.get(p).kind==='directory')state.closed=state.closed.filter(id=>id!==p);
            else if(!state.expanded.includes(p))state.expanded.push(p);
          }
          state.mode='relations';state.target=n.id;$('mode').value=state.mode;
        }else{
          Object.assign(state,reveal(data,state,n.id));$('mode').value=state.mode;
          $('selection').textContent=n.label+'\n'+n.file;render();return;
        }}
        select(n);};row.appendChild(button);fragment.appendChild(row);}
    if(nodes.length>100){const note=document.createElement('p');note.textContent=`另有 ${nodes.length-100} 个匹配，请细化搜索。`;fragment.appendChild(note);}
    if(!nodes.length){const note=document.createElement('p');note.textContent='没有匹配的节点。';fragment.appendChild(note);}
    $('node-list').replaceChildren(fragment);
  }
  $('repo-name').textContent=data.repository.name;$('depth').value=String(state.depth);$('mode').value=state.mode;
  $('source').textContent='源码 '+data.repository.source_fingerprint.slice(0,16)+' · 静态 Python 关系，未覆盖全部运行时调用';
  for(const kind of kinds){const label=document.createElement('label'), input=document.createElement('input');input.type='checkbox';input.checked=true;input.setAttribute('aria-label',labels[kind]);input.onchange=()=>{state.kinds=Array.from($('filters').querySelectorAll('input')).filter(x=>x.checked).map(x=>x.value);render();};input.value=kind;label.style.color=data.colors[kind];label.append(input,document.createTextNode(labels[kind]));$('filters').appendChild(label);}
  $('mode').onchange=()=>{state.mode=$('mode').value;render();};$('depth').onchange=()=>{state.depth=Number($('depth').value);render();};$('tests').onchange=()=>{state.tests=$('tests').checked;render();};$('search').oninput=list;
  $('reset').onclick=()=>{state.target=null;state.selected=null;state.closed=data.nodes.filter(n=>n.kind==='directory'&&n.id!=='dir:.').map(n=>n.id);state.expanded=[];$('search').value='';$('selection').textContent='选择一个节点查看其结构位置。';render();};$('fit').onclick=()=>fit();$('zoom-in').onclick=()=>zoom(.8);$('zoom-out').onclick=()=>zoom(1.25);
  $('canvas').addEventListener('pointerdown',e=>{if(e.target.closest('g[data-node-id]'))return;dragging={x:e.clientX,y:e.clientY,camera:{...camera}};$('canvas').setPointerCapture(e.pointerId);});
  $('canvas').addEventListener('pointermove',e=>{if(!dragging)return;const box=svg.getBoundingClientRect(),scale=Math.max(camera.w/(box.width||960),camera.h/(box.height||600));camera.x=dragging.camera.x-(e.clientX-dragging.x)*scale;camera.y=dragging.camera.y-(e.clientY-dragging.y)*scale;applyCamera();});
  $('canvas').addEventListener('wheel',e=>{e.preventDefault();const box=svg.getBoundingClientRect(),scale=Math.max(camera.w/(box.width||960),camera.h/(box.height||600));camera.x+=e.deltaX*scale;camera.y+=e.deltaY*scale;applyCamera();},{passive:false});
  $('canvas').addEventListener('pointerup',()=>{dragging=null;});$('canvas').addEventListener('pointercancel',()=>{dragging=null;});
  $('export').onclick=()=>{const copy=svg.cloneNode(true);copy.setAttribute('viewBox',`0 0 ${view.width} ${view.height}`);copy.setAttribute('width',String(view.width));copy.setAttribute('height',String(view.height));
    const blob=new Blob([new XMLSerializer().serializeToString(copy)],{type:'image/svg+xml;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='repo-map-'+state.mode+'.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  render();
})();
