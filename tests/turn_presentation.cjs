const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const b=await chromium.launch({channel:'chrome',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});const p=await b.newPage({viewport:{width:1440,height:1800}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.route('**/body_panel.js',async r=>{const response=await r.fetch();await r.fulfill({response,body:(await response.text()).replace('this.container=container;','window.flyTest=this;this.container=container;').replace('new THREE.WebGLRenderer({','new THREE.WebGLRenderer({preserveDrawingBuffer:true,')})});
 await p.route('**/app.js',async r=>{const response=await r.fetch();await r.fulfill({response,body:(await response.text()).replaceAll('requestAnimationFrame(animate)','void 0')+'\nwindow.paintOnce=()=>animate(performance.now());'})});
 await p.addInitScript(()=>{const WS=window.WebSocket;window.WebSocket=class extends WS{constructor(...args){super(...args);window.wsTest=this;this.addEventListener('open',()=>this.send(JSON.stringify({action:'speed',value:.5})));const paused=new Set();this.addEventListener('message',e=>{const s=JSON.parse(e.data);window.stateTest=s;if(s.running&&s.time>=4.75&&s.trial<2&&!paused.has(s.trial)){paused.add(s.trial);this.send(JSON.stringify({action:'pause'}))}})}}});
 await p.goto('http://localhost:8501/?version=turn-comparison');await p.waitForFunction(()=>window.stateTest?.running===false,undefined,{polling:100,timeout:90000});
 await p.locator('#steering-gain').selectOption('1');await p.waitForFunction(()=>stateTest.steering_gain===1,undefined,{polling:100,timeout:90000});await p.locator('#steering-gain').selectOption('2');await p.waitForFunction(()=>stateTest.steering_gain===2,undefined,{polling:100,timeout:90000});console.log('GAIN controls passed');await p.evaluate(()=>window.paintOnce());const left=await p.evaluate(()=>({turn:stateTest.response_turn_deg,top:flyTest.topView,up:flyTest.camera.up.toArray(),canvas:!!document.querySelector('.turn-comparison')}));if(!left.top||!left.canvas||left.turn<=0)throw Error(JSON.stringify(left));
 console.log('LEFT',left);await p.evaluate(()=>window.paintOnce());await p.screenshot({path:'demo-preview.png',fullPage:false,timeout:90000});
 await p.locator('.fly-view-toggle').click();if(await p.evaluate(()=>flyTest.topView))throw Error('Side view failed');await p.locator('.fly-view-toggle').click();
 await p.evaluate(()=>{wsTest.send(JSON.stringify({action:'next'}));wsTest.send(JSON.stringify({action:'play'}))});await p.waitForFunction(()=>window.stateTest?.trial===1&&!window.stateTest.running&&window.stateTest.time>=4.75,undefined,{polling:100,timeout:90000});
 const right=await p.evaluate(()=>stateTest.response_turn_deg);if(right>=0)throw Error('Right response not negative');
 await p.evaluate(()=>window.paintOnce());await p.screenshot({path:'right-turn-preview.png',fullPage:false,timeout:90000});
 await p.setViewportSize({width:390,height:4200});await p.waitForTimeout(500);if(!await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1))throw Error('Mobile overflow');
 await p.evaluate(()=>window.paintOnce());await p.screenshot({path:'mobile-preview.png',fullPage:false,timeout:90000});
 fs.writeFileSync('data/validation/turn-presentation.json',JSON.stringify({left,right,viewToggle:true,mobile:true,errors},null,2));if(errors.length)throw Error(errors.join(','));console.log(JSON.stringify({left,right,errors}));await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
