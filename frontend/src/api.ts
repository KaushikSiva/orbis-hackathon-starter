export interface Product {id:string;name:string;brand?:string;category:string;price:number|null;source?:string;price_status?:string;price_quote?:string;retrieved_at?:string;currency?:string;image_url?:string;source_url:string;dimensions?:string|Record<string,unknown>;reason?:string;rationale?:string;}
export interface Directive {id:string;instruction:string;prompt:string;status:string;created_at:string;message?:string;}
export interface Room {id:string;name:string;budget:number;preferences:string[];keep:string[];image_url:string|null;directives:Directive[];products:Product[];total:number;unpriced_count?:number;product_source?:string;graph:{status:string;explanation?:string;[key:string]:unknown};exports:{id?:string;url?:string;title?:string;type?:string;sharing?:{recipient:string;status:string;message:string;role:string};[key:string]:unknown}[];}
export interface Health {status:string;integrations:Record<string,{configured:boolean;status:string;message?:string}>;}
export interface Preview {approval_id:string;title:string;content:string;shopping_rows:unknown[];share_recipient?:string|null;}
export async function api<T>(path:string,body?:unknown,method?:string):Promise<T>{
 const response=await fetch(path,{method:method||(body?'POST':'GET'),headers:body instanceof FormData?undefined:body?{'Content-Type':'application/json'}:undefined,body:body instanceof FormData?body:body?JSON.stringify(body):undefined});
 const data=await response.json().catch(()=>({detail:'The service returned an unreadable response.'}));
 if(!response.ok){const detail=data.detail;throw new Error(typeof detail==='string'?detail:detail?.message||data.message||`Request failed (${response.status}). Please retry.`);}
 return data;
}
export const money=(value:number)=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:value%1?2:0}).format(value);
