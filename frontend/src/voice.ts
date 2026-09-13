import {useEffect,useRef,useState} from 'react';
import {api} from './api';
export type VoiceTarget='direction'|'products';
export function useVoiceInput(onText:(text:string,target:VoiceTarget)=>void){
 const [state,setState]=useState<'idle'|'requesting'|'recording'|'transcribing'>('idle');
 const [target,setTarget]=useState<VoiceTarget|null>(null);const [error,setError]=useState('');
 const recorder=useRef<MediaRecorder|null>(null),media=useRef<MediaStream|null>(null),timer=useRef<number|undefined>(undefined),epoch=useRef(0),result=useRef(onText);result.current=onText;
 const release=()=>{clearTimeout(timer.current);media.current?.getTracks().forEach(t=>t.stop());media.current=null;};
 const cancel=()=>{epoch.current++;if(recorder.current?.state==='recording')recorder.current.stop();release();recorder.current=null;setState('idle');setTarget(null);};
 useEffect(()=>()=>{epoch.current++;if(recorder.current?.state==='recording')recorder.current.stop();release();},[]);
 const start=async(next:VoiceTarget)=>{
  if(state!=='idle')return;
  const run=++epoch.current;setError('');setTarget(next);setState('requesting');
  try{
   if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined')throw new Error('Voice recording is unavailable in this browser. Please type your request.');
   const stream=await navigator.mediaDevices.getUserMedia({audio:true});
   if(run!==epoch.current){stream.getTracks().forEach(t=>t.stop());return;}
   media.current=stream;const mime=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(type=>MediaRecorder.isTypeSupported(type));
   const rec=new MediaRecorder(stream,mime?{mimeType:mime}:undefined);recorder.current=rec;const chunks:Blob[]=[];
   rec.ondataavailable=event=>{if(event.data.size)chunks.push(event.data);};
   rec.onerror=()=>{if(run!==epoch.current)return;cancel();setError('Recording failed. Try again or type your request.');};
   rec.onstop=async()=>{
    if(run!==epoch.current)return;release();setState('transcribing');
    try{
     const audio=new Blob(chunks,{type:rec.mimeType});if(!audio.size)throw new Error('No audio was recorded. Please try again.');
     const form=new FormData();form.append('file',audio,rec.mimeType.includes('mp4')?'voice.mp4':rec.mimeType.includes('ogg')?'voice.ogg':'voice.webm');
     const response=await api<{text:string}>('/api/transcriptions',form);
     if(run===epoch.current)result.current(response.text,next);
    }catch(err){if(run===epoch.current)setError(err instanceof Error?err.message:'Transcription failed. Please try typing.');}
    finally{if(run===epoch.current){setState('idle');setTarget(null);recorder.current=null;}}
   };
   rec.start();setState('recording');timer.current=window.setTimeout(()=>{if(run===epoch.current&&rec.state==='recording')rec.stop();},45000);
  }catch(err){if(run!==epoch.current)return;release();if(run===epoch.current){setState('idle');setTarget(null);setError(err instanceof Error?err.message:'Microphone access failed. Please type your request.');}}
 };
 const stop=()=>{if(recorder.current?.state==='recording')recorder.current.stop();};
 return {state,target,error,start,stop,cancel,clearError:()=>setError(''),message:state==='recording'?'Recording · stop to transcribe with OpenAI (45-second limit).':state==='transcribing'?'Transcribing with OpenAI…':state==='requesting'?'Allow microphone access to record.':''};
}
