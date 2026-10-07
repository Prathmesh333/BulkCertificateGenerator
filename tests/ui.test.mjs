import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';

const html=await readFile('app/static/index.html','utf8');
const code=await readFile('app/static/studio.js','utf8');

function studio(){
 const dom=new JSDOM(html,{url:'http://localhost/',runScripts:'outside-only'});
 const w=dom.window;
 w.matchMedia=()=>({matches:true});
 w.ResizeObserver=class{observe(){}};
 Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 600;}});
 w.HTMLCanvasElement.prototype.getContext=()=>({measureText:text=>({width:text.length*10})});
 w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLElement.prototype.setPointerCapture=()=>{};
 w.fetch=async (url)=>({ok:true,json:async()=>url.includes('/images')?{image_id:'image',width:1400,height:990,url:'/image.png'}:url.includes('/sheets')?{sheet_id:'sheet',columns:['Name','Number'],rows:[{Name:'Demo Name',Number:'001'},{Name:'Demo Recipient',Number:'002'}],total:2}:url==='/builder/jobs'?{job_id:'job'}:url.includes('/recipients')?{items:[{name:'Demo Name',status:'succeeded',download_url:'/certificate.pdf'}]}:{status:'completed',progress_percent:100,counts:{succeeded:2,failed:0,pending:0,processing:0}}});
 w.eval(code);
 return {w,dom,$:id=>w.document.getElementById(id)};
}
async function load(w){await w.eval("imageUpload(new File(['x'],'design.png'))");await w.eval("sheetUpload(new File(['x'],'names.csv'))");}

test('upload, place layers, change colors, undo and redo',async()=>{
 const {w,dom,$}=studio();
 assert.equal($('generate').disabled,true);
 await load(w);
 $('columns').firstChild.click();
 assert.equal(w.document.querySelectorAll('.placed').length,1);
 assert.equal($('generate').disabled,false);
 assert.equal($('layers').firstChild.getAttribute('aria-pressed'),'true');
 w.document.querySelector('[data-color="#8b5cf6"]').click();
 assert.equal($('color').value,'#8b5cf6');
 $('undo').click();assert.equal($('color').value,'#203040');
 $('redo').click();assert.equal($('color').value,'#8b5cf6');
 $('remove').click();assert.equal(w.document.querySelectorAll('.placed').length,0);
 $('undo').click();assert.equal(w.document.querySelectorAll('.placed').length,1);
 dom.window.close();
});

test('zoom, guides, keyboard placement, and preview recipient',async()=>{
 const {w,dom,$}=studio();await load(w);$('columns').firstChild.click();
 $('grid-toggle').click();assert.equal($('grid-toggle').getAttribute('aria-pressed'),'true');
 $('zoom-in').click();assert.equal($('zoom-label').textContent,'125%');
 $('zoom-reset').click();assert.equal($('zoom-label').textContent,'100%');
 const before=Number($('field-x').value);
 w.document.querySelector('.placed').dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
 assert.equal(Number($('field-x').value),before+1);
 $('preview-row').value='1';$('preview-row').dispatchEvent(new w.Event('change'));
 assert.equal(w.document.querySelector('.placed').textContent,'Demo Recipient');
 $('motion-toggle').click();assert.equal(w.document.body.classList.contains('motion-paused'),true);
 dom.window.close();
});

test('generation submits design and shows terminal download state',async()=>{
 const {w,dom,$}=studio();await load(w);$('columns').firstChild.click();
 let submitted;
 const original=w.fetch;
 w.fetch=async(url,options)=>{if(url==='/builder/jobs')submitted=JSON.parse(options.body);return original(url,options);};
 $('generate').click();
 await new Promise(resolve=>setTimeout(resolve,20));
 assert.equal(submitted.fields[0].column,'Name');
 assert.equal(submitted.name_column,'Name');
 assert.equal($('progress').value,100);
 assert.equal($('zip-download').hidden,false);
 assert.equal($('job-results').querySelector('a').getAttribute('href'),'/certificate.pdf');
 assert.equal($('generate').disabled,false);
 dom.window.close();
});

test('drag locks to pointer and records a reversible move',async()=>{
 const {w,dom,$}=studio();await load(w);$('columns').firstChild.click();
 const before=Number($('field-x').value),node=w.document.querySelector('.placed');
 node.dispatchEvent(new w.MouseEvent('pointerdown',{clientX:200,clientY:200,bubbles:true}));
 node.onpointermove({clientX:220,clientY:220});node.onpointerup();
 assert.ok(Number($('field-x').value)>before);
 $('undo').click();assert.equal(Number($('field-x').value),before);
 dom.window.close();
});

test('rectangle resizing, page alignment and snapping',async()=>{
 const {w,dom,$}=studio();await load(w);$('columns').firstChild.click();
 const handle=w.document.querySelector('.resize-handle');
 const before=Number($('field-width').value);
 handle.onpointerdown({clientX:200,pointerId:1,stopPropagation(){}});
 handle.onpointermove({clientX:220});handle.onpointerup();
 assert.ok(Number($('field-width').value)>before);
 w.document.querySelector('[data-place="center"]').click();
 assert.equal(Number($('field-x').value),148.5);
 w.eval('const f=selected();f.x_mm=150;snapField(f,2);');
 assert.equal(w.eval('selected().x_mm'),148.5);
 assert.ok($('snap-guides').children.length);
 dom.window.close();
});

test('text alignment changes do not move the rectangle',async()=>{
 const {w,dom,$}=studio();await load(w);$('columns').firstChild.click();
 const before=w.eval('boxLeft(selected())');
 $('align').value='left';$('align').dispatchEvent(new w.Event('input'));
 assert.equal(w.eval('boxLeft(selected())'),before);
 $('align').value='right';$('align').dispatchEvent(new w.Event('input'));
 assert.equal(w.eval('boxLeft(selected())'),before);
 dom.window.close();
});

test('floating toolbar follows selection and edits the selected field',async()=>{
 const {w,dom,$}=studio();assert.equal($('floating-tools').hidden,true);
 await load(w);$('columns').firstChild.click();assert.equal($('floating-tools').hidden,false);
 $('quick-font').value='Times-Roman';$('quick-font').dispatchEvent(new w.Event('input'));
 $('quick-bold').click();assert.equal($('font').value,'Times-Bold');
 $('quick-size').value='30';$('quick-size').dispatchEvent(new w.Event('input'));
 assert.equal(w.eval('selected().font_size_pt'),30);
 w.document.querySelector('[data-text-align="right"]').click();assert.equal(w.eval('selected().align'),'right');
 $('canvas').dispatchEvent(new w.MouseEvent('pointerdown',{bubbles:true}));assert.equal($('floating-tools').hidden,true);
 dom.window.close();
});
