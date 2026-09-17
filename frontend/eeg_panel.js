export function canvasContext(canvas){
  const dpr=Math.min(devicePixelRatio,2),w=canvas.clientWidth,h=canvas.clientHeight;
  if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr)}
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);return {ctx,w,h};
}
export class EEGPanel{
  constructor(canvas){this.canvas=canvas;this.trial=null;this.previous=null}
  setTrial(trial){this.previous=this.trial;this.trial=trial}
  render(time){
    const {ctx:c,w,h}=canvasContext(this.canvas),left=30,right=w-12,top=15,bottom=h-17;
    c.lineWidth=.5;c.strokeStyle='#20333d';
    for(let x=left;x<right;x+=(right-left)/8){c.beginPath();c.moveTo(x,top);c.lineTo(x,bottom);c.stroke()}
    const row=(bottom-top)/8;
    for(let i=0;i<8;i++){
      const y=top+row*(i+.5);c.strokeStyle='#20333d';c.setLineDash([2,4]);c.beginPath();c.moveTo(left,y);c.lineTo(right,y);c.stroke();c.setLineDash([]);
      c.fillStyle=i===2||i===4?'#94c6bd':'#627e88';c.font='9px Consolas,monospace';c.fillText(this.trial?.channels[i]||['Fz','FC1','C3','Cz','C4','CP1','CP2','Pz'][i],2,y+3);
      if(!this.trial)continue;
      // A rolling four-second window. Blank before the first real sample.
      // At the trial boundary use the previous actual trial, never synthesize a trace.
      const cursor=Math.min(4,time),rate=this.trial.sample_rate;
      c.save();c.beginPath();c.rect(left,y-row*.46,right-left,row*.92);c.clip();
      c.beginPath();c.strokeStyle=i===2||i===4?'#75dec9':'#529f95';c.lineWidth=i===2||i===4?1.2:.85;
      let started=false;
      for(let j=0;j<500;j++){
        const sampleTime=cursor-4+j/125;let v;
        if(sampleTime>=0)v=this.trial.signals[i][Math.min(499,Math.floor(sampleTime*rate))];
        else if(this.previous)v=this.previous.signals[i][Math.max(0,Math.min(499,Math.floor((4+sampleTime)*rate)))];
        if(v===undefined){started=false;continue}
        const x=left+j/499*(right-left),sy=y-v*(row*.85/100);
        if(!started){c.moveTo(x,sy);started=true}else c.lineTo(x,sy);
      }
      c.stroke();c.restore();
    }
    c.strokeStyle='#7ae5ce99';c.lineWidth=.8;c.beginPath();c.moveTo(right,top);c.lineTo(right,bottom);c.stroke();
  }
}
