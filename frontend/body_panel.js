import * as THREE from './vendor/three.module.js';
import {t} from './i18n.js';

// Compiled MuJoCo mesh vertices + live geom_xpos/geom_xmat. No scripted poses.
export class FlyPanel {
  constructor(container,bodyGeometry){
    this.container=container;this.state=null;this.visual=[];
    this.scene=new THREE.Scene();this.scene.background=new THREE.Color('#09141b');
    this.camera=new THREE.PerspectiveCamera(40,1,.03,1500);this.camera.up.set(0,0,1);
    this.renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));
    this.renderer.shadowMap.enabled=true;this.renderer.shadowMap.type=THREE.PCFSoftShadowMap;
    container.appendChild(this.renderer.domElement);
    this.scene.add(new THREE.HemisphereLight('#d9f8ff','#203528',2.3));
    this.light=new THREE.DirectionalLight('#fff3d7',3);this.light.position.set(4,-4,8);this.light.castShadow=true;
    this.light.shadow.mapSize.set(1024,1024);Object.assign(this.light.shadow.camera,{left:-5,right:5,top:5,bottom:-5,near:.1,far:30});
    this.light.shadow.bias=-.0003;this.scene.add(this.light);this.scene.add(this.light.target);
    const rim=new THREE.DirectionalLight('#58c8dc',1.5);rim.position.set(-3,5,3);this.scene.add(rim);
    const floor=new THREE.Mesh(new THREE.PlaneGeometry(1500,1500),new THREE.MeshStandardMaterial({color:'#12252d',roughness:.96}));
    floor.receiveShadow=true;floor.position.z=-.02;this.scene.add(floor);
    this.grid=new THREE.GridHelper(200,200,'#31515b','#213940');this.grid.rotation.x=Math.PI/2;this.grid.position.z=-.008;
    this.grid.material.transparent=true;this.grid.material.opacity=.4;this.scene.add(this.grid);
    const geometryMap={};
    for(const [id,m] of Object.entries(bodyGeometry.meshes)){
      const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(m.vertices,3));g.setIndex(m.faces);g.computeVertexNormals();geometryMap[id]=g;
    }
    this.meshes=bodyGeometry.geoms.map(g=>{
      const c=new THREE.Color().setRGB(...g.rgba.slice(0,3));
      const material=new THREE.MeshStandardMaterial({color:c,roughness:.55,metalness:.06,side:THREE.DoubleSide,transparent:g.rgba[3]<1,opacity:g.rgba[3]});
      const mesh=new THREE.Mesh(geometryMap[g.mesh_id],material);mesh.name=g.name||'';mesh.castShadow=true;mesh.receiveShadow=true;
      this.scene.add(mesh);this.visual.push({p:new THREE.Vector3(),q:new THREE.Quaternion(),ready:false});return mesh;
    });
    const pg=new THREE.BufferGeometry();this.pathArray=new Float32Array(2000*3);pg.setAttribute('position',new THREE.BufferAttribute(this.pathArray,3));pg.setDrawRange(0,0);
    this.trail=new THREE.Line(pg,new THREE.LineBasicMaterial({color:'#657780',transparent:true,opacity:.35}));this.trail.frustumCulled=false;this.scene.add(this.trail);
    const responseGeometry=new THREE.BufferGeometry();this.responseArray=new Float32Array(100*3);responseGeometry.setAttribute('position',new THREE.BufferAttribute(this.responseArray,3));responseGeometry.setDrawRange(0,0);
    this.responseTrail=new THREE.Line(responseGeometry,new THREE.LineBasicMaterial({color:'#66d9c1'}));this.responseTrail.frustumCulled=false;this.scene.add(this.responseTrail);
    this.positionMarker=new THREE.Mesh(new THREE.RingGeometry(.10,.14,32),new THREE.MeshBasicMaterial({color:'#66d9c1',side:THREE.DoubleSide}));this.scene.add(this.positionMarker);
    this.target=new THREE.Mesh(new THREE.SphereGeometry(.13,16,12),new THREE.MeshStandardMaterial({color:'#c7eb8b',emissive:'#7da047',emissiveIntensity:.65}));this.scene.add(this.target);
    this.targetRing=new THREE.Mesh(new THREE.RingGeometry(.29,.31,40),new THREE.MeshBasicMaterial({color:'#bde786',side:THREE.DoubleSide,transparent:true,opacity:.65}));this.scene.add(this.targetRing);
    this.minimap=document.createElement('canvas');this.minimap.className='physics-minimap';this.minimap.width=160;this.minimap.height=120;container.appendChild(this.minimap);
    this.topView=true;
    this.viewButton=document.createElement('button');this.viewButton.className='fly-view-toggle';this.viewButton.textContent=t('view-top');container.appendChild(this.viewButton);
    this.viewButton.addEventListener('pointerdown',e=>e.stopPropagation());
    this.viewButton.onclick=()=>{this.topView=!this.topView;this.viewButton.textContent=this.topView?t('view-top'):t('view-side')};
    this.turnCanvas=document.createElement('canvas');this.turnCanvas.className='turn-comparison';this.turnCanvas.width=720;this.turnCanvas.height=320;container.parentElement.insertAdjacentElement('afterend',this.turnCanvas);
    this.headingArrow=new THREE.ArrowHelper(new THREE.Vector3(1,0,0),new THREE.Vector3(),2.8,0x65e2d3,.5,.25);this.scene.add(this.headingArrow);
    const referenceGeometry=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(),new THREE.Vector3(2.8,0,0)]);
    this.referenceArrow=new THREE.Line(referenceGeometry,new THREE.LineDashedMaterial({color:0xa8b5c0,dashSize:.16,gapSize:.12}));this.referenceArrow.computeLineDistances();this.scene.add(this.referenceArrow);
    this.center=new THREE.Vector3();this.offset=new THREE.Vector3(2.7,-4.2,3.5);this.zoom=1.3;this.azimuth=0;
    let drag=null;
    container.addEventListener('pointerdown',e=>{drag=e.clientX;container.setPointerCapture(e.pointerId)});
    container.addEventListener('pointermove',e=>{if(drag!==null){this.azimuth+=(e.clientX-drag)*.008;drag=e.clientX}});
    container.addEventListener('pointerup',()=>drag=null);container.addEventListener('pointercancel',()=>drag=null);
    container.addEventListener('wheel',e=>{e.preventDefault();this.zoom=THREE.MathUtils.clamp(this.zoom+e.deltaY*.001,.65,3)}, {passive:false});
    new ResizeObserver(()=>this.resize()).observe(container);this.resize();
  }
  resize(){const w=this.container.clientWidth,h=this.container.clientHeight;this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.renderer.setSize(w,h)}
  reset(){this.visual.forEach(v=>v.ready=false);this.centerReady=false}
  update(s){
    this.state=s;this.viewButton.textContent=this.topView?t('view-top'):t('view-side');const body=s.body,matrix=new THREE.Matrix4();
    this.targetPoses=body.geometry_positions.map((p,i)=>{
      const r=body.geometry_rotations[i];matrix.set(r[0],r[1],r[2],0,r[3],r[4],r[5],0,r[6],r[7],r[8],0,0,0,0,1);
      return {p:new THREE.Vector3(...p),q:new THREE.Quaternion().setFromRotationMatrix(matrix)};
    });
    const path=body.path.slice(-2000);path.forEach((p,i)=>this.pathArray.set([p[0],p[1],.009],i*3));
    this.trail.geometry.attributes.position.needsUpdate=true;this.trail.geometry.setDrawRange(0,path.length);
    this.positionMarker.position.set(body.position[0],body.position[1],.012);
    const response=s.response_path||[];response.forEach((p,i)=>this.responseArray.set([p[0],p[1],.018],i*3));
    this.responseTrail.geometry.attributes.position.needsUpdate=true;this.responseTrail.geometry.setDrawRange(0,response.length);
    this.responseTrail.material.color.set(s.lesion?'#83909b':s.response_turn_deg<0?'#84aaff':'#66d9c1');
    this.target.position.set(s.target.x,s.target.y,.16);this.targetRing.position.set(s.target.x,s.target.y,.015);this.drawMinimap();this.drawTurnComparison();
  }
  drawMinimap(){
    const s=this.state,c=this.minimap.getContext('2d'),w=160,h=120;c.clearRect(0,0,w,h);c.fillStyle='#07131de0';c.fillRect(0,0,w,h);
    const pts=[...s.body.path,[s.target.x,s.target.y],s.body.position],xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);
    const minX=Math.min(...xs)-1,maxX=Math.max(...xs)+1,minY=Math.min(...ys)-1,maxY=Math.max(...ys)+1,scale=Math.min((w-18)/(maxX-minX),(h-28)/(maxY-minY));
    const xy=p=>[9+(p[0]-minX)*scale,h-9-(p[1]-minY)*scale];
    c.strokeStyle='#52606a';c.lineWidth=1;c.beginPath();s.body.path.forEach((p,i)=>{const [x,y]=xy(p);i?c.lineTo(x,y):c.moveTo(x,y)});c.stroke();
    c.strokeStyle=s.lesion?'#83909b':s.response_turn_deg<0?'#84aaff':'#66d9c1';c.lineWidth=2.5;c.beginPath();(s.response_path||[]).forEach((p,i)=>{const [x,y]=xy(p);i?c.lineTo(x,y):c.moveTo(x,y)});c.stroke();
    for(const [p,color,r]of [[s.body.position,'#e9eee0',3],[[s.target.x,s.target.y],'#c7eb8b',2.8]]){const [x,y]=xy(p);c.fillStyle=color;c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fill()}
    const [hx,hy]=xy(s.body.position),angle=-s.body.heading;
    c.save();c.translate(hx,hy);c.rotate(angle);c.strokeStyle='#e9eee0';c.beginPath();c.moveTo(0,0);c.lineTo(11,0);c.lineTo(7,-3);c.moveTo(11,0);c.lineTo(7,3);c.stroke();c.restore();
    c.fillStyle='#7797a5';c.font='9px Consolas,monospace';c.fillText(t('minimap-title'),8,12);c.fillText(t('minimap-axis'),8,24);
  }
  drawTurnComparison(){
    const s=this.state,c=this.turnCanvas.getContext('2d'),w=720,h=320;
    const active=(s.response_path||[]).length>0,delta=(s.response_turn_deg||0)*Math.PI/180;
    if(s.lesion){c.clearRect(0,0,w,h);c.fillStyle='#09151d';c.fillRect(0,0,w,h);c.fillStyle='#e6b48e';c.font='bold 32px Segoe UI';c.fillText(t('bt-cut-title'),28,64);c.fillStyle='#adc0cb';c.font='22px Segoe UI';c.fillText(t('bt-cut-lr'),28,112);c.fillText(t('bt-cut-walk'),28,154);c.font='bold 42px Consolas';c.fillText(t('bt-cut-drift')+(s.cut_turn_deg||0).toFixed(1)+'°',28,222);c.font='20px Segoe UI';c.fillText(t('bt-cut-real'),28,280);return;}
    const color=delta<0?'#84aaff':'#65e2d3',cx=172,cy=217,r=139;
    c.clearRect(0,0,w,h);c.fillStyle='#09151d';c.fillRect(0,0,w,h);
    c.font='20px "Segoe UI",sans-serif';c.fillStyle='#c4d7df';c.fillText(t('bt-turn-title'),24,32);
    c.strokeStyle='#263e4a';c.lineWidth=2;c.beginPath();c.arc(cx,cy,r,Math.PI,Math.PI*2);c.stroke();
    const arrow=(angle,stroke,dashed)=>{c.save();c.translate(cx,cy);c.rotate(angle);c.strokeStyle=stroke;c.lineWidth=dashed?3:6;c.setLineDash(dashed?[9,8]:[]);c.beginPath();c.moveTo(0,0);c.lineTo(0,-r);c.stroke();c.setLineDash([]);c.beginPath();c.moveTo(-12,-r+19);c.lineTo(0,-r);c.lineTo(12,-r+19);c.stroke();c.restore()};
    arrow(0,'#788d9a',true);if(active)arrow(-delta,color,false);
    if(active){c.fillStyle=delta<0?'#84aaff30':'#65e2d330';c.beginPath();c.moveTo(cx,cy);c.arc(cx,cy,r,-Math.PI/2,-Math.PI/2-delta,delta>0);c.closePath();c.fill();}
    c.fillStyle=color;c.font='bold 44px "Segoe UI",sans-serif';
    c.fillText(active?(Math.abs(s.response_turn_deg)<1?t('bt-responding'):delta>=0?t('bt-left'):t('bt-right')):t('bt-wait'),356,116);
    c.font='bold 56px Consolas,monospace';c.fillText(active?Math.abs(s.response_turn_deg).toFixed(1)+'°':'—',356,181);
    c.fillStyle='#94a9b5';c.font='19px "Segoe UI",sans-serif';c.fillText(t('bt-dashed'),356,225);c.fillStyle=color;c.fillText(t('bt-solid'),356,255);
    c.fillStyle='#758e9c';c.font='17px "Segoe UI",sans-serif';c.fillText(t('bt-axis'),24,295);
  }
  render(){
    if(this.state&&this.targetPoses){
      // Body meshes and trail must use the same authoritative physics snapshot.
      // Independently smoothing the meshes makes the path lead the visible body.
      this.meshes.forEach((mesh,i)=>{const t=this.targetPoses[i];mesh.position.copy(t.p);mesh.quaternion.copy(t.q)});
      const target=new THREE.Vector3(...this.state.body.position);target.z=.7;
      target.x-=.4*Math.cos(this.state.body.heading);target.y-=.4*Math.sin(this.state.body.heading);
      if(this.topView||!this.centerReady){this.center.copy(target);this.centerReady=true}else this.center.lerp(target,.13);
      const offset=this.offset.clone().applyAxisAngle(new THREE.Vector3(0,0,1),this.azimuth).multiplyScalar(this.zoom);
      if(this.topView){this.camera.up.set(0,1,0);this.camera.position.copy(this.center).add(new THREE.Vector3(0,0,8*this.zoom));}
      else{this.camera.up.set(0,0,1);this.camera.position.copy(this.center).add(offset)}
      this.camera.lookAt(this.center);
      const body=this.state.body,heading=body.heading,baseline=heading-(this.state.response_turn_deg||0)*Math.PI/180;
      const origin=new THREE.Vector3(body.position[0],body.position[1],2.3);
      this.headingArrow.setColor((this.state.response_turn_deg||0)<0?0x84aaff:0x65e2d3);this.headingArrow.position.copy(origin);this.headingArrow.setDirection(new THREE.Vector3(Math.cos(heading),Math.sin(heading),0));
      this.referenceArrow.position.copy(origin);this.referenceArrow.rotation.z=baseline;
      this.referenceArrow.visible=(this.state.response_path||[]).length>0;
      this.headingArrow.visible=this.topView&&!this.state.lesion;this.referenceArrow.visible=this.referenceArrow.visible&&this.topView&&!this.state.lesion;
      this.light.position.copy(this.center).add(new THREE.Vector3(4,-4,8));this.light.target.position.copy(this.center);
      this.grid.position.x=Math.round(this.center.x);this.grid.position.y=Math.round(this.center.y);
    }
    this.renderer.render(this.scene,this.camera);
  }
}
