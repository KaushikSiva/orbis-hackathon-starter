import {useEffect,useRef,useState,type RefObject} from 'react';
import fixWebmDuration from 'fix-webm-duration';
export interface RoomClip {id:string;roomId:string;createdAt:string;duration:number;blob:Blob;saved:boolean;}
function database():Promise<IDBDatabase>{return new Promise((resolve,reject)=>{const req=indexedDB.open('showroom-recordings',1);req.onupgradeneeded=()=>req.result.createObjectStore('clips',{keyPath:'id'});req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});}
async function storeClip(clip:RoomClip){const db=await database();try{await new Promise<void>((resolve,reject)=>{const tx=db.transaction('clips','readwrite');tx.objectStore('clips').put({...clip,saved:true});tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});}finally{db.close();}}
async function loadClips(roomId:string){const db=await database();try{return await new Promise<RoomClip[]>((resolve,reject)=>{const req=db.transaction('clips').objectStore('clips').getAll();req.onsuccess=()=>resolve((req.result as RoomClip[]).filter(c=>c.roomId===roomId).sort((a,b)=>b.createdAt.localeCompare(a.createdAt)));req.onerror=()=>reject(req.error);});}finally{db.close();}}
export function useRecordings(roomId:string|undefined,video:RefObject<HTMLVideoElement|null>,heldFrame:RefObject<HTMLCanvasElement|null>,held:boolean,live:boolean,active:boolean){
 const [clips,setClips]=useState<RoomClip[]>([]),[recording,setRecording]=useState(false),[saving,setSaving]=useState(false),[seconds,setSeconds]=useState(0),[error,setError]=useState('');
 const recorder=useRef<MediaRecorder|null>(null),finalizing=useRef<Promise<RoomClip|null>|null>(null),stopResolve=useRef<((clip:RoomClip|null)=>void)|null>(null),cleanup=useRef<()=>void>(()=>{}),autoStarted=useRef(false),mounted=useRef(true);
 const current=useRef({roomId,held});current.current={roomId,held};
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;cleanup.current();if(recorder.current?.state!=='inactive')recorder.current?.stop();};},[]);
 useEffect(()=>{let cancelled=false;setClips([]);if(roomId)void loadClips(roomId).then(list=>{if(!cancelled)setClips(previous=>[...previous,...list.filter(c=>!previous.some(p=>p.id===c.id))]);}).catch(()=>{if(!cancelled)setError('Browser storage is unavailable. Download clips to keep them.');});return()=>{cancelled=true;};},[roomId]);
 const finish=():Promise<RoomClip|null>=>{
  if(finalizing.current)return finalizing.current;
  const rec=recorder.current;if(!rec||rec.state==='inactive')return Promise.resolve(null);
  finalizing.current=new Promise(resolve=>{stopResolve.current=resolve;});
  setSaving(true);setRecording(false);cleanup.current();rec.stop();return finalizing.current;
 };
 const start=()=>{
  if(recorder.current||finalizing.current||!current.current.roomId)return;
  const element=video.current;if(!element||!element.videoWidth||element.readyState<2){setError('Wait for the first live frame before recording.');return;}
  try{
   if(typeof MediaRecorder==='undefined')throw Error('Video recording is unavailable in this browser.');
   const canvas=document.createElement('canvas');canvas.width=Math.min(1280,element.videoWidth);canvas.height=Math.round(canvas.width*element.videoHeight/element.videoWidth);
   const ctx=canvas.getContext('2d')!;const draw=()=>{const source=current.current.held&&heldFrame.current?.width?heldFrame.current:video.current;if(source)try{ctx.drawImage(source,0,0,canvas.width,canvas.height);}catch{/* Hold the last decoded frame during disconnect. */}};draw();
   const media=canvas.captureStream(24);const mime=['video/webm;codecs=vp8','video/webm','video/mp4'].find(type=>MediaRecorder.isTypeSupported(type));
   let rec:MediaRecorder;try{rec=new MediaRecorder(media,{...(mime?{mimeType:mime}:{}),videoBitsPerSecond:1_600_000});}catch(e){media.getTracks().forEach(t=>t.stop());throw e;}
   const id=crypto.randomUUID(),owner=current.current.roomId,createdAt=new Date().toISOString(),started=performance.now(),chunks:Blob[]=[];let bytes=0;
   recorder.current=rec;setError('');setSeconds(0);
   const drawTimer=window.setInterval(draw,1000/24),clock=window.setInterval(()=>setSeconds(Math.floor((performance.now()-started)/1000)),500),limit=window.setTimeout(()=>{setError('The 10-minute recording was saved. Start a new clip to keep recording.');void finish();},600000);
   const unload=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue='';};window.addEventListener('beforeunload',unload);
   cleanup.current=()=>{clearInterval(drawTimer);clearInterval(clock);clearTimeout(limit);window.removeEventListener('beforeunload',unload);};
   rec.ondataavailable=event=>{if(event.data.size){chunks.push(event.data);bytes+=event.data.size;}if(bytes>120*1024*1024&&rec.state==='recording'){setError('The recording reached its size limit and was saved.');void finish();}};
   rec.onerror=()=>{setError('Recording stopped unexpectedly. Any captured frames will be saved.');void finish();};
   rec.onstop=async()=>{
    const duration=(performance.now()-started)/1000;cleanup.current();media.getTracks().forEach(t=>t.stop());if(mounted.current){setSaving(true);setRecording(false);}let clip:RoomClip|null=null;
    try{
     if(!chunks.length)throw Error('No video frames were captured. Try recording again.');
     let blob=new Blob(chunks,{type:rec.mimeType});if(rec.mimeType.includes('webm'))blob=await fixWebmDuration(blob,duration*1000,{logger:false});
     clip={id,roomId:owner,createdAt,duration,blob,saved:false};
     try{await storeClip(clip);clip.saved=true;}catch{if(mounted.current)setError('Clip ready, but browser storage is full or unavailable. Download it before leaving.');}
     if(mounted.current&&current.current.roomId===owner)setClips(list=>[clip!,...list]);
    }catch(err){if(mounted.current)setError(err instanceof Error?err.message:'The recording could not be saved.');}
    finally{recorder.current=null;finalizing.current=null;if(mounted.current)setSaving(false);stopResolve.current?.(clip);stopResolve.current=null;}
   };
   rec.start(1000);setRecording(true);
  }catch(err){setError(err instanceof Error?err.message:'Recording is unavailable.');}
 };
 useEffect(()=>{if(!active){autoStarted.current=false;void finish();}else if(live&&!autoStarted.current&&roomId){autoStarted.current=true;start();}},[active,live,roomId]);
 return {clips,recording,saving,seconds,error,start,finish,clearError:()=>setError('')};
}
export const clipTime=(seconds:number)=>`${Math.floor(seconds/60)}:${Math.floor(seconds%60).toString().padStart(2,'0')}`;
