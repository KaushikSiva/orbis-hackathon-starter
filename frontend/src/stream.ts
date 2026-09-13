import { Reactor, type ReactorMessage } from '@reactor-team/js-sdk';
import { useRef,useState,useEffect } from 'react';
import {api,type Room} from './api';
type Phase='idle'|'connecting'|'priming'|'live'|'pausing'|'paused'|'resuming'|'disconnected'|'error';
function acknowledged(reactor:Reactor,command:string,data:Record<string,unknown>,expected:string){
 return new Promise<ReactorMessage>((resolve,reject)=>{
  const timer=window.setTimeout(()=>finish(new Error(`Orbis did not acknowledge ${command.replaceAll('_',' ')}. Try reconnecting.`)),90000);
  const listener=(message:ReactorMessage)=>{if(message.type===expected)finish(undefined,message);if(message.type==='command_error')finish(new Error(String((message.data as Record<string,unknown>)?.message||'Orbis rejected the instruction.')));};
  const finish=(error?:Error,message?:ReactorMessage)=>{clearTimeout(timer);reactor.off('message',listener);if(error)reject(error);else resolve(message!);};
  reactor.on('message',listener);
  void reactor.sendCommand(command,data).catch(error=>finish(error));
 });
}
async function roomFrame(source:string){
 const blob=await fetch(source).then(response=>{if(!response.ok)throw new Error('The room image could not be loaded. Upload it again.');return response.blob();});
 const bitmap=await createImageBitmap(blob);
 const canvas=document.createElement('canvas');canvas.width=1280;canvas.height=736;
 const ctx=canvas.getContext('2d')!;const scale=Math.max(canvas.width/bitmap.width,canvas.height/bitmap.height);
 ctx.drawImage(bitmap,(canvas.width-bitmap.width*scale)/2,(canvas.height-bitmap.height*scale)/2,bitmap.width*scale,bitmap.height*scale);bitmap.close();
 return new Promise<Blob>((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error('Unable to prepare this photo. Try a JPG or PNG.')),'image/jpeg',0.92));
}
export function useRoomStream(){
 const reactor=useRef<Reactor|null>(null);const active=useRef(false);const epoch=useRef(0);const video=useRef<HTMLVideoElement>(null);
 const heldFrame=useRef<HTMLCanvasElement>(null);const motion=useRef<'running'|'pausing'|'paused'|'resuming'>('running');const [held,setHeld]=useState(false);
 const holdFrame=()=>{const element=video.current,canvas=heldFrame.current;if(element&&canvas&&element.readyState>=2&&element.videoWidth){canvas.width=element.videoWidth;canvas.height=element.videoHeight;canvas.getContext('2d')?.drawImage(element,0,0);setHeld(true);}element?.pause();};
 const [phase,setPhase]=useState<Phase>('idle');const [error,setError]=useState('');const [detail,setDetail]=useState('');const [frames,setFrames]=useState(0);const [prompt,setPrompt]=useState('');const [sessionId,setSessionId]=useState('');
 useEffect(()=>()=>{epoch.current++;active.current=false;void reactor.current?.disconnect().catch(()=>{});},[]);
 const stop=async()=>{epoch.current++;active.current=false;const previous=reactor.current;reactor.current=null;setPhase('idle');setFrames(0);setError('');setHeld(false);motion.current='running';if(video.current)video.current.srcObject=null;void previous?.disconnect().catch(()=>{});};
 const start=async(room:Room)=>{
  await stop();const run=++epoch.current;const current=()=>run===epoch.current;let client:Reactor|null=null;setError('');setFrames(0);setPhase('connecting');setDetail('Preparing a private Orbis session…');active.current=true;
  try{
   const token=await api<{jwt:string;model:string;api_url:string;prompt:string}>('/api/reactor/token',{room_id:room.id});
   if(!current())return;client=new Reactor({modelName:token.model,apiUrl:token.api_url,jwt:token.jwt,readyTimeoutMs:240000,controlRequestTimeoutMs:90000,modelTracks:[{name:'main_video',kind:'video',direction:'recvonly'},{name:'main_audio',kind:'audio',direction:'recvonly'}],logLevel:'error'});reactor.current=client;
   let conditionsReady=false;
   client.on('sessionIdChanged',id=>{if(current())setSessionId(id||'');});
   client.on('statusChanged',status=>{if(!current())return;if(status==='waiting')setDetail('Orbis is warming up. This can take a few minutes.');if(status==='disconnected'&&active.current){active.current=false;setPhase('disconnected');setError('The live session disconnected. Your room and shopping list are saved. Reconnect to continue.');}});
   client.on('error',err=>{if(!current())return;setError(/429|capacity|rate.limit/i.test(err.message)?'Orbis is at capacity. Your room is saved — retry when a session opens.':err.message);});
   client.on('message',message=>{if(!current())return;
    const data=(message.data||{}) as Record<string,unknown>;
    window.dispatchEvent(new CustomEvent('showroom:stream-event',{detail:{type:message.type,at:new Date().toISOString(),frames_emitted:data.frames_emitted,delivered:data.delivered,current_prompt:data.current_prompt}}));
    if(message.type==='conditions_ready')conditionsReady=true;
    if(message.type==='state'&&typeof data.current_prompt==='string')setPrompt(data.current_prompt);
    if(message.type==='generation_paused'){if(motion.current!=='pausing')holdFrame();motion.current='paused';setPhase('paused');setDetail('Room paused. Direct the next change, then resume.');}
    if(message.type==='generation_resumed'){motion.current='resuming';setPhase('resuming');setDetail('Resuming the same room…');void video.current?.play().then(playing).catch(()=>setError('Playback could not resume. Use Resume playback to try again.'));}
    if(message.type==='generation_started'){setPhase('priming');setDetail('Your room is taking shape. Waiting for the first video frames…');}
    if(message.type==='chunk_complete'&&typeof data.frames_emitted==='number')setFrames(count=>count+(data.frames_emitted as number));
    if(message.type==='command_error'){setError(String(data.message||data.error||'Orbis rejected the command. Please try a different instruction.'));}
    if(message.type==='generation_complete'){active.current=false;setPhase('disconnected');setDetail('This generation has finished. Start another session to continue.');}
   });
   client.on('trackReceived',(name,_track,stream)=>{if(!current())return;if(name==='main_video'&&video.current){video.current.srcObject=stream;void video.current.play().catch(()=>setDetail('Press play to view the live room.'));}});
   await client.connect();if(!current())return;
   setDetail('Sending your room photograph…');
   const frame=await roomFrame(room.image_url||'/images/sample-room.jpg');if(!current())return;const file=await client.uploadFile(frame,{name:'room-reference.jpg'});if(!current())return;
   await acknowledged(client,'set_image',{image:file},'image_accepted');if(!current())return;
   await acknowledged(client,'set_prompt',{prompt:token.prompt},'prompt_accepted');if(!current())return;
   if(!conditionsReady){const readyClient=client;await new Promise<void>((resolve,reject)=>{const timeout=window.setTimeout(()=>{readyClient.off('message',listener);reject(new Error('Orbis has not confirmed that the room is ready. Reconnect to try again.'));},15000);const listener=(message:ReactorMessage)=>{if(message.type==='conditions_ready'){clearTimeout(timeout);readyClient.off('message',listener);resolve();}};readyClient.on('message',listener);});}
   if(!current())return;setPhase('priming');setDetail('Starting the room preview. First frames may take a moment…');await client.sendCommand('start',{});
  }catch(err){if(!current())return;active.current=false;setPhase('error');setError(err instanceof Error?err.message:'Unable to start Orbis. Please retry.');void client?.disconnect().catch(()=>{});}
 };
 const steer=async(instructionPrompt:string)=>{if(!reactor.current||!['live','paused'].includes(phase))throw new Error('Start or pause the live room before sending a direction.');return acknowledged(reactor.current,'set_prompt',{prompt:instructionPrompt},'prompt_accepted');};
 // Orbis pause/resume stops generation at a chunk boundary, preserving model history.
 // https://www.reactor.inc/models/visko-orbis-dynamic/api#pause
 const pause=async()=>{
  const client=reactor.current;if(!client||phase!=='live')return;
  const run=epoch.current;motion.current='pausing';holdFrame();setPhase('pausing');setError('');setDetail('Holding this frame. Waiting for Orbis to pause…');
  try{await acknowledged(client,'pause',{},'generation_paused');}
  catch(error){if(run!==epoch.current||!active.current)return;motion.current='running';setHeld(false);setPhase('live');void video.current?.play().catch(()=>{});throw error;}
 };
 const resume=async()=>{
  const client=reactor.current;if(!client||phase!=='paused')return;
  const run=epoch.current;motion.current='resuming';setPhase('resuming');setError('');setDetail('Resuming the same room…');
  try{await acknowledged(client,'resume',{},'generation_resumed');}
  catch(error){if(run!==epoch.current||!active.current)return;motion.current='paused';setPhase('paused');throw error;}
 };
 const playing=()=>{
  const run=epoch.current,element=video.current;
  const show=()=>{if(active.current&&run===epoch.current&&['running','resuming'].includes(motion.current)){
   motion.current='running';setHeld(false);setPhase('live');setError('');setDetail('Live from Orbis');
   window.dispatchEvent(new CustomEvent('showroom:stream-event',{detail:{type:'browser_frame_presented',at:new Date().toISOString(),width:element?.videoWidth,height:element?.videoHeight}}));
  }};
  if(element?.requestVideoFrameCallback)element.requestVideoFrameCallback(show);else if(element&&element.readyState>=2&&element.videoWidth>0)show();
 };
 const retryPlayback=async()=>{await video.current?.play();playing();};
 return {phase,error,detail,frames,prompt,sessionId,video,heldFrame,held,start,stop,steer,pause,resume,playing,retryPlayback,clearError:()=>setError('')};
}
