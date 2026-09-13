import {useEffect,useRef,useState,type MouseEvent} from 'react';
import {ArrowUpRight,LoaderCircle,ShoppingBag,X} from 'lucide-react';
import {money,type Product,type Room} from './api';
type Source=HTMLVideoElement|HTMLCanvasElement|HTMLImageElement;
export function sourcePoint(width:number,height:number,box:{width:number;height:number},fit:string,position:string,x:number,y:number){
 const scale=fit==='contain'?Math.min(box.width/width,box.height/height):Math.max(box.width/width,box.height/height);
 const parts=position.split(' ');const fraction=(value:string)=>value?.endsWith('%')?parseFloat(value)/100:.5;
 const px=(x-(box.width-width*scale)*fraction(parts[0]))/scale/width,py=(y-(box.height-height*scale)*fraction(parts[1]))/scale/height;
 return px<0||py<0||px>1||py>1?null:{x:px,y:py};
}
export function FrameShop({getSource,ensureRoom,replaying}:{getSource:()=>Source|null;ensureRoom:()=>Promise<Room>;replaying:boolean}){
 const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState<{selection:{label:string;query:string;brand?:string|null;colors?:string[];material?:string;shape?:string;brand_status?:string};products:Product[]}|null>(null),[frame,setFrame]=useState('');
 const request=useRef<AbortController|null>(null),epoch=useRef(0),snapshot=useRef<{blob:Blob;x:number;y:number}|null>(null);
 useEffect(()=>()=>{request.current?.abort();},[]);useEffect(()=>()=>{if(frame)URL.revokeObjectURL(frame);},[frame]);
 const close=()=>{epoch.current++;request.current?.abort();setOpen(false);setBusy(false);};
 const search=async()=>{
  const shot=snapshot.current;if(!shot)return;const run=++epoch.current;request.current?.abort();const controller=new AbortController();request.current=controller;setBusy(true);setError('');setResult(null);
  try{const room=await ensureRoom();if(run!==epoch.current)return;const body=new FormData();body.append('file',shot.blob,'selected-frame.jpg');body.append('x',String(shot.x));body.append('y',String(shot.y));
   const response=await fetch(`/api/rooms/${room.id}/visual-search`,{method:'POST',body,signal:controller.signal});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Visual search failed. Please try another piece.');if(run===epoch.current)setResult(data);
  }catch(err){if(run===epoch.current)setError(err instanceof Error?err.message:'Visual search failed.');}finally{if(run===epoch.current)setBusy(false);}
 };
 const select=async(event:MouseEvent<HTMLButtonElement>)=>{
  const source=getSource();if(!source)return;let run=epoch.current;
  try{
   const width=source instanceof HTMLVideoElement?source.videoWidth:source instanceof HTMLImageElement?source.naturalWidth:source.width,height=source instanceof HTMLVideoElement?source.videoHeight:source instanceof HTMLImageElement?source.naturalHeight:source.height;
   if(!width||!height)throw Error('Wait for the room frame to load, then click a piece.');
   const rect=source.getBoundingClientRect(),style=getComputedStyle(source);const point=sourcePoint(width,height,rect,style.objectFit,style.objectPosition,event.detail===0?rect.width/2:event.clientX-rect.left,event.detail===0?rect.height/2:event.clientY-rect.top);
   if(!point)return;request.current?.abort();run=++epoch.current;
   const canvas=document.createElement('canvas');canvas.width=Math.min(width,1280);canvas.height=Math.round(canvas.width*height/width);canvas.getContext('2d')!.drawImage(source,0,0,canvas.width,canvas.height);
   const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(Error('Frame capture failed.')),'image/jpeg',.88));if(run!==epoch.current)return;
   snapshot.current={blob,...point};setFrame(URL.createObjectURL(blob));setOpen(true);await search();
  }catch(err){if(run===epoch.current){setOpen(true);setError(err instanceof Error?err.message:'Unable to capture this frame.');setBusy(false);}}
 };
 return <><button type="button" className={`frame-target ${replaying?'over-replay':''}`} aria-label="Find Amazon matches for an item in this frame" title="Click a piece to find similar items on Amazon" onClick={event=>void select(event)}><span className="frame-hint"><ShoppingBag size={13}/> Click a piece to shop</span></button>{open&&<aside className="visual-results" aria-label="Selected furniture matches"><div className="visual-results-heading"><span>SIMILAR ON AMAZON</span><button type="button" aria-label="Close furniture matches" onClick={close}><X size={17}/></button></div>{frame&&<img className="selected-frame" src={frame} alt="Frame selected for furniture search"/>}{busy?<p role="status"><LoaderCircle className="spin" size={16}/> Identifying your piece and finding matches…</p>:error?<div role="alert"><p>{error}</p>{snapshot.current&&<button className="text-button" onClick={()=>void search()}>Retry this frame</button>}</div>:result&&<><strong>{result.selection.label}</strong><p>{[result.selection.brand?`Brand marking: ${result.selection.brand}`:'Brand unknown', ...(result.selection.colors||[]), result.selection.material, result.selection.shape].filter(Boolean).join(' · ')}</p><p>Visual matches, not an exact product identification.</p><div className="visual-match-list">{result.products.slice(0,3).map(product=><a key={product.id} href={product.source_url} target="_blank" rel="noreferrer"><span>{product.name}</span><b>{product.price===null?'Check price':money(product.price)} <ArrowUpRight size={13}/></b></a>)}</div></>}<small>Prices may use cached pages up to 6 hours old. Your shopping list stays unchanged.</small></aside>}</>;
}
