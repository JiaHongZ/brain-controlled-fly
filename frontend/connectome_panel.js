import * as THREE from './vendor/three.module.js';

const PALETTE={sensory:'#70e5d5',central:'#72b7cb',descending:'#b1a6ef',VNC:'#6b9bed',motor:'#c7eb8b'};
export class ConnectomePanel {
  constructor(container, graph) {
    this.container=container; this.graph=graph; this.activities=new Float32Array(graph.nodes.length);
    this.target=new Float32Array(graph.nodes.length); this.scene=new THREE.Scene();
    this.camera=new THREE.PerspectiveCamera(42,1,.1,100); this.camera.position.set(0,.1,7.4); this.camera.lookAt(0,-.4,0);
    this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'high-performance'});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,2)); container.appendChild(this.renderer.domElement);
    this.group=new THREE.Group(); this.scene.add(this.group); this.group.position.y=.25;
    const positions=new Float32Array(graph.nodes.length*3), colors=new Float32Array(positions.length);
    graph.nodes.forEach((n,i)=>{positions.set([n.x,n.y,n.z],i*3); const c=new THREE.Color(PALETTE[n.region]||'#7db8cb'); colors.set([c.r,c.g,c.b],i*3)});
    const geometry=new THREE.BufferGeometry(); geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));
    geometry.setAttribute('color',new THREE.BufferAttribute(colors,3)); geometry.setAttribute('activity',new THREE.BufferAttribute(this.activities,1));
    geometry.setAttribute('emphasis',new THREE.Float32BufferAttribute(graph.nodes.map(n=>n.cell_type==='DNa02'?2.2:1),1));
    const material=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,vertexColors:true,
      uniforms:{pixelRatio:{value:Math.min(devicePixelRatio,2)}},
      vertexShader:`attribute float activity; attribute float emphasis; varying vec3 vColor; varying float vActivity; uniform float pixelRatio;
        void main(){vColor=color;vActivity=activity;vec4 mv=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*mv;
        gl_PointSize=(3.8+activity*7.)*emphasis*pixelRatio*(6./-mv.z);}`,
      fragmentShader:`varying vec3 vColor;varying float vActivity;void main(){float d=length(gl_PointCoord-.5)*2.;if(d>1.)discard;
        float glow=exp(-d*d*4.);vec3 c=mix(vColor,vec3(.85,1.,.94),vActivity*.6);
        gl_FragColor=vec4(c,glow*(.65+vActivity*.35));}`});
    this.points=new THREE.Points(geometry,material); this.group.add(this.points);
    const ep=new Float32Array(graph.edges.length*6); this.edgeColors=new Float32Array(ep.length);
    graph.edges.forEach((e,i)=>{ep.set(positions.subarray(e.source*3,e.source*3+3),i*6);ep.set(positions.subarray(e.target*3,e.target*3+3),i*6+3)});
    this.linesGeometry=new THREE.BufferGeometry();this.linesGeometry.setAttribute('position',new THREE.BufferAttribute(ep,3));
    this.linesGeometry.setAttribute('color',new THREE.BufferAttribute(this.edgeColors,3));
    this.lines=new THREE.LineSegments(this.linesGeometry,new THREE.ShaderMaterial({vertexColors:true,transparent:true,blending:THREE.AdditiveBlending,depthWrite:false,
      vertexShader:'varying vec3 vColor; void main(){vColor=color;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
      fragmentShader:'varying vec3 vColor;void main(){gl_FragColor=vec4(vColor,.20);}'}));
    this.group.add(this.lines);
    let down=null;
    container.addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY];container.setPointerCapture(e.pointerId)});
    container.addEventListener('pointermove',e=>{if(down){this.group.rotation.y+=(e.clientX-down[0])*.007;this.group.rotation.x=THREE.MathUtils.clamp(this.group.rotation.x+(e.clientY-down[1])*.005,-.7,.7);down=[e.clientX,e.clientY]}});
    container.addEventListener('pointerup',()=>down=null);container.addEventListener('pointercancel',()=>down=null);
    container.addEventListener('wheel',e=>{e.preventDefault();this.camera.position.z=THREE.MathUtils.clamp(this.camera.position.z+e.deltaY*.003,4.5,11)}, {passive:false});
    this.inspector=document.createElement('div');this.inspector.className='neuron-inspector';this.inspector.hidden=true;container.appendChild(this.inspector);
    const ray=new THREE.Raycaster();ray.params.Points.threshold=.045;let lastHover=0;
    container.addEventListener('pointermove',e=>{if(down||performance.now()-lastHover<80)return;lastHover=performance.now();
      const box=container.getBoundingClientRect();ray.setFromCamera(new THREE.Vector2((e.clientX-box.left)/box.width*2-1,-(e.clientY-box.top)/box.height*2+1),this.camera);
      const hits=ray.intersectObject(this.points);this.inspector.hidden=hits.length===0;
      if(hits.length){const n=graph.nodes[hits[0].index];this.inspector.textContent=`MANC #${n.node_id} · ${n.cell_type}\n${n.cell_class} · ${n.side} · ${n.predicted_nt}`;}
    });container.addEventListener('pointerleave',()=>this.inspector.hidden=true);
    this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(container);this.resize();
  }
  resize(){const w=this.container.clientWidth,h=this.container.clientHeight;this.renderer.setSize(w,h);this.camera.aspect=w/h;this.camera.updateProjectionMatrix()}
  reset(){this.group.rotation.set(0,0,0);this.camera.position.z=7.4}
  update(activity){this.target.set(activity)}
  render(time, running=true){
    const a=this.activities;
    for(let i=0;i<a.length;i++) a[i]=this.target[i];
    this.points.geometry.attributes.activity.needsUpdate=true;
    this.graph.edges.forEach((e,i)=>{const v=Math.pow(Math.min(a[e.source],a[e.target]),1.5);const c=e.weight<.1?.3:1;const side=this.graph.nodes[e.source].side;
      const rgb=side==='L'?[.27,.86,.77]:side==='R'?[.33,.59,1]:[.5,.6,.7];
      for(let j=0;j<2;j++){this.edgeColors[i*6+j*3]=(.008+v*rgb[0]*.18)*c;this.edgeColors[i*6+j*3+1]=(.018+v*rgb[1]*.18)*c;this.edgeColors[i*6+j*3+2]=(.025+v*rgb[2]*.18)*c;}});
    this.linesGeometry.attributes.color.needsUpdate=true;
    this.renderer.render(this.scene,this.camera);
  }
}
