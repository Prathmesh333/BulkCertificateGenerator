import * as THREE from './vendor/three.module.js';

const host = document.getElementById('three-scene');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
let renderer;
try {
  renderer = new THREE.WebGLRenderer({alpha:true, antialias:true, powerPreference:'low-power'});
} catch {
  // The CSS illustration remains available without WebGL.
}
if (renderer) {
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
  host.append(renderer.domElement);
  host.parentElement.classList.add('has-webgl');
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35,1,.1,100);
  camera.position.set(0,0,9);
  scene.add(new THREE.HemisphereLight(0xffffff,0x8b67aa,3));
  const light = new THREE.DirectionalLight(0xfff2d8,4);
  light.position.set(2,3,5);scene.add(light);
  const group = new THREE.Group();scene.add(group);
  const textureCanvas=document.createElement('canvas');textureCanvas.width=1024;textureCanvas.height=720;
  const ctx=textureCanvas.getContext('2d');
  ctx.fillStyle='#fffcf0';ctx.fillRect(0,0,1024,720);
  ctx.strokeStyle='#bb9150';ctx.lineWidth=6;ctx.strokeRect(28,28,968,664);
  ctx.lineWidth=1;ctx.strokeRect(40,40,944,640);
  ctx.textAlign='center';ctx.fillStyle='#665079';ctx.font='22px Georgia';ctx.fillText('CERTIFICATE OF ACHIEVEMENT',512,160);
  ctx.fillStyle='#9b899e';ctx.font='17px Arial';ctx.fillText('A moment worth celebrating',512,235);
  ctx.fillStyle='#624977';ctx.font='italic 62px Georgia';ctx.fillText('Well deserved.',512,360);
  ctx.strokeStyle='#cbb9d5';ctx.beginPath();ctx.moveTo(330,400);ctx.lineTo(694,400);ctx.stroke();
  ctx.fillStyle='#947fa2';ctx.font='16px Arial';ctx.fillText('CREATED FOR SOMEONE EXTRAORDINARY',512,480);
  ctx.fillStyle='#c69751';ctx.font='65px Georgia';ctx.fillText('✳',512,610);
  const texture=new THREE.CanvasTexture(textureCanvas);texture.colorSpace=THREE.SRGBColorSpace;
  const card=new THREE.Mesh(new THREE.BoxGeometry(3.6,2.5,.04),[
    new THREE.MeshStandardMaterial({color:0xd3bfa0}),new THREE.MeshStandardMaterial({color:0xd3bfa0}),
    new THREE.MeshStandardMaterial({color:0xd3bfa0}),new THREE.MeshStandardMaterial({color:0xd3bfa0}),
    new THREE.MeshStandardMaterial({map:texture,roughness:.7}),new THREE.MeshStandardMaterial({color:0xf4e9d4})
  ]);
  card.rotation.set(-.1,-.3,-.15);group.add(card);
  const objects=[];
  for(const [geometry,color,x,y,z] of [
    [new THREE.TorusGeometry(.43,.13,12,40),0xb89ce5,-2.1,.8,.2],
    [new THREE.OctahedronGeometry(.36),0xf1a484,2,.9,.3],
    [new THREE.SphereGeometry(.28,20,14),0xaed5bb,-1.8,-1.1,.5],
    [new THREE.BoxGeometry(.4,.4,.4),0xf0d48c,2,-.8,.2]
  ]) {const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,roughness:.35,metalness:.1}));mesh.position.set(x,y,z);mesh.userData.base=y;group.add(mesh);objects.push(mesh);}
  let visible=true,paused=document.body.classList.contains('motion-paused'),running=false,start=performance.now(),pointer={x:0,y:0};
  const draw=()=>renderer.render(scene,camera);
  function animate(time){
    if(!visible||document.hidden||paused||reduced.matches){running=false;draw();return;}
    const t=(time-start)/1000;
    group.rotation.y=THREE.MathUtils.lerp(group.rotation.y,pointer.x*.13,.035);
    group.rotation.x=THREE.MathUtils.lerp(group.rotation.x,-pointer.y*.08,.035);
    card.position.y=Math.sin(t*.7)*.07;
    objects.forEach((mesh,i)=>{mesh.rotation.x=t*.2+i;mesh.rotation.z=t*.16+i;mesh.position.y=mesh.userData.base+Math.sin(t*.8+i)*.12;});
    draw();requestAnimationFrame(animate);
  }
  function resume(){if(!running&&visible&&!document.hidden&&!paused&&!reduced.matches){running=true;requestAnimationFrame(animate);}else if(!running)draw();}
  const resize=new ResizeObserver(()=>{const {width,height}=host.getBoundingClientRect();if(!width||!height)return;renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix();draw();});resize.observe(host);
  const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;resume();});observer.observe(host);
  document.querySelector('.intro').addEventListener('pointermove',event=>{const bounds=host.getBoundingClientRect();pointer={x:Math.max(-1,Math.min(1,(event.clientX-bounds.left)/bounds.width*2-1)),y:(event.clientY-bounds.top)/bounds.height*2-1};});
  document.addEventListener('visibilitychange',resume);reduced.addEventListener('change',resume);
  document.addEventListener('studio-motion',event=>{paused=event.detail.paused;resume();});
  renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();visible=false;host.parentElement.classList.remove('has-webgl');});
  window.addEventListener('pagehide',()=>{visible=false;resize.disconnect();observer.disconnect();texture.dispose();group.traverse(object=>{object.geometry?.dispose();const materials=object.material?(Array.isArray(object.material)?object.material:[object.material]):[];materials.forEach(m=>m.dispose());});renderer.dispose();});
  resume();
}
