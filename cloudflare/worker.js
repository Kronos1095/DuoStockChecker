const PRODUCT='MK1E4LL/A';
const APPLE='https://www.apple.com/shop/buy-iphone/iphone-duo';
const ATT='https://www.att.com/buy/phones/apple-iphone-duo-256gb-star-white.html';
async function jsonRequest(url,body){
 const response=await fetch(url,{method:body?'POST':'GET',body:body?JSON.stringify(body):undefined,headers:{Accept:'application/json','Content-Type':'application/json'},signal:AbortSignal.timeout(8000)});
 if(!response.ok)throw Error(`HTTP ${response.status}`);
 return response.json();
}
export function appleStores(data){
 const stores=data?.body?.stores;
 if(!Array.isArray(stores)||!stores.length)throw Error('No validated stores');
 return stores.filter(s=>['NY','NJ'].includes(s.state)&&s.storeNumber).map(s=>({id:s.storeNumber,name:s.storeName,status:['available','unavailable'].includes(s.partsAvailability?.[PRODUCT]?.pickupDisplay)?s.partsAvailability[PRODUCT].pickupDisplay:'unknown'}));
}
export class StockMonitor{
 constructor(state,env){this.state=state;this.env=env;}
 async fetch(request){
  const path=new URL(request.url).pathname;
  if(path==='/start'){
   const config=await request.json();await this.state.storage.put('retailer',config.retailer);
   await this.state.storage.setAlarm(Date.now()+1000);return Response.json({started:config.retailer});
  }
  if(path==='/test'){
   try{
    const receipt=await this.push('Duo Stock Watch TEST','TEST: Stock checker notification delivery check.',APPLE);
    return Response.json({provider:receipt.provider||'ntfy',providerAccepted:true,messageId:receipt.id});
   }catch(e){return Response.json({providerAccepted:false,error:e.message},{status:502});}
  }
  return Response.json({...await this.state.storage.get('status')||{health:'not_started'},notification:await this.state.storage.get('notification')||{state:'not_tested'}});
 }
 async push(title,message,link){
  try{
   if(this.env.TELEGRAM_BOT_TOKEN){
    const chatId=(this.env.TELEGRAM_CHAT_ID||'').trim();
    if(!/^-?\d+$/.test(chatId))throw Error('TELEGRAM_CHAT_ID is missing or invalid');
    let response;
    try{response=await fetch('https://api.telegram.org/bot'+this.env.TELEGRAM_BOT_TOKEN.trim()+'/sendMessage',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chat_id:chatId,text:title+'\n'+message+'\n'+link,disable_notification:false}),signal:AbortSignal.timeout(10000)});}
    catch{throw Error('Telegram connection failed or timed out');}
    const receipt=await response.json().catch(()=>({}));
    if(!response.ok||!receipt.ok)throw Error('Telegram rejected message (HTTP '+response.status+')');
    await this.state.storage.put('notification',{state:'accepted_by_telegram',at:new Date().toISOString(),messageId:receipt.result.message_id});
    return {id:receipt.result.message_id,provider:'telegram'};
   }
   const topic=(this.env.NTFY_TOPIC||'').trim();
   if(!topic)throw Error('NTFY_TOPIC is missing');
   if(!/^[A-Za-z0-9_-]{1,64}$/.test(topic))throw Error('NTFY_TOPIC must be the topic name only (no URL, spaces, or slashes)');
   const headers={'Content-Type':'application/json'};
   if(this.env.NTFY_TOKEN)headers.Authorization=`Bearer ${this.env.NTFY_TOKEN.trim()}`;
   const response=await fetch('https://ntfy.sh/'+encodeURIComponent(topic),{method:'POST',headers:{...headers,'Content-Type':'text/plain; charset=utf-8',Title:title,Priority:'5',Tags:'iphone,rotating_light',Click:link},body:message,signal:AbortSignal.timeout(20000)});
   const receipt=await response.json().catch(()=>({}));
   if(!response.ok)throw Error(`ntfy HTTP ${response.status}${receipt.code?' (code '+receipt.code+')':''}`);
   if(receipt.event!=='message'||!receipt.id)throw Error('ntfy returned no message receipt');
   await this.state.storage.put('notification',{state:'accepted_by_ntfy',at:new Date().toISOString(),messageId:receipt.id});
   return receipt;
  }catch(e){
   await this.state.storage.put('notification',{state:'failed',at:new Date().toISOString(),error:e.message});
   throw e;
  }
 }
 async alarm(){
  const retailer=await this.state.storage.get('retailer')||'Apple';
  const interval=retailer==='Apple'?30000:120000;
  // Arm next invocation before work so exceptions cannot permanently stop monitoring.
  await this.state.storage.setAlarm(Date.now()+interval);
  const now=Date.now();let status;
  try{
   let stores=[],message,searches=[];
   if(retailer==='Apple'){
    const zip=this.env.APPLE_HOT_ZIP||'10001';
    const data=await jsonRequest(`https://www.apple.com/shop/retail/pickup-message?pl=true&location=${encodeURIComponent(zip)}&parts.0=${encodeURIComponent(PRODUCT)}`);
    stores=appleStores(data);message=`Nearby Apple stores for ZIP ${zip}; target interval 30 seconds.`;
   }else{
    const zips=['10001','10314','11530','11755','10601','10954','12203','13204','14225','14564','07001','07601','07470','07866','08807','07728','08648','08002','08053','08401','10451','11201','11373','11746'];
    const offset=await this.state.storage.get('offset')||0;
    const selected=[0,1,2,3].map(i=>zips[(offset+i)%zips.length]);
    searches=await Promise.all(selected.map(async zip=>{
     try{
      const d=await jsonRequest(`https://www.att.com/msapi/sales/uis/v1/inventory/storeavailability?zipCode=${zip}`,{itemDetails:[{category:'phone',billCode:'6050G'}]});
      if(d.error?.errorId?.toUpperCase()==='UIS-INV-00003')return{zip,status:'unavailable',stores:[]};
      if(d.error||!Array.isArray(d.content?.storeList))throw Error('Invalid response');
      return{zip,status:'checked',stores:d.content.storeList.filter(s=>['NY','NJ'].includes(s.region)).map(s=>({id:s.inv_id||s.id,name:s.mystore_name||s.name,status:s.availableQuantity!=null&&Number.isFinite(Number(s.availableQuantity))?(Number(s.availableQuantity)>0?'available':'unavailable'):'unknown'}))};
     }catch{return{zip,status:'unknown',stores:[]};}
    }));
    stores=searches.flatMap(s=>s.stores);await this.state.storage.put('offset',(offset+4)%zips.length);
    message='AT&T: four rotating ZIP areas every 2 minutes; each area approximately every 12 minutes. Not complete store coverage.';
   }
   const observed=await this.state.storage.get('observed')||{};
   const outbox=await this.state.storage.get('outbox')||[];
   for(const s of stores){
    if(!s.id||!['available','unavailable'].includes(s.status))continue;
    if(s.status==='available'&&observed[s.id]!=='available')outbox.push({created:now,attempts:0,message:`${retailer}: ${s.name} — Star White 256GB reported available. Confirm and reserve now.`});
    observed[s.id]=s.status;
   }
   await this.state.storage.put({observed,outbox,failures:0});
   status={retailer,health:searches.some(s=>s.status==='unknown')?'partial':'ok',updated:new Date(now).toISOString(),message,stores,searches,notificationsConfigured:!!(this.env.TELEGRAM_BOT_TOKEN&&this.env.TELEGRAM_CHAT_ID||this.env.NTFY_TOPIC)};
  }catch{
   const failures=(await this.state.storage.get('failures')||0)+1;
   await this.state.storage.put('failures',failures);
   await this.state.storage.setAlarm(Date.now()+Math.min(300000,interval*2**Math.min(failures,4)));
   status={retailer,health:'error',updated:new Date(now).toISOString(),stores:[],message:'Request failed; backing off. No current stock result.'};
  }
  const test=await this.state.storage.get('test');
  if(test&&now>=(test.notBefore||0)&&now-test.created<120000){try{await this.push('Duo Stock Watch TEST',test.message,APPLE);await this.state.storage.delete('test');status.testAcceptedAt=new Date().toISOString();}catch{status.notificationError='Test delivery failed';}}
  const pending=await this.state.storage.get('outbox')||[],remaining=[];
  for(const item of pending){
   if(now-item.created>120000||item.attempts>=4)continue;
   try{await this.push('Duo pickup available',item.message,retailer==='Apple'?APPLE:ATT);status.lastPushAcceptedAt=new Date().toISOString();}
   catch{remaining.push({...item,attempts:item.attempts+1});status.notificationError='Push failed; bounded retry pending';}
  }
  await this.state.storage.put({outbox:remaining,status});
 }
}
export default{
 async fetch(request,env){
  const url=new URL(request.url);
  if(url.pathname==='/setup')return new Response("<!doctype html><html><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Duo Stock Watch controls</title><style>body{font:18px system-ui;max-width:650px;margin:30px auto;padding:20px;background:#101827;color:#fff}input,button{font:inherit;padding:14px;margin:10px 0;box-sizing:border-box;width:100%}pre{white-space:pre-wrap;font-size:14px}a{color:#aecbff}</style><h1>Duo Stock Watch</h1><p>Enter the ADMIN_TOKEN you saved in Cloudflare. It stays in this page's memory and is sent only to this Worker's protected controls.</p><input type=\"password\" id=\"token\" autocomplete=\"off\" placeholder=\"ADMIN_TOKEN\"><button id=\"start\">Start Apple and AT&T checks</button><button id=\"test\">Send test now</button><p>The result below reports Telegram or ntfy acceptance, or the delivery error.</p><a href=\"/status\">View current status</a><pre id=\"result\"></pre><script>async function send(path){const out=document.getElementById('result');out.textContent='Sending…';try{const r=await fetch(path,{method:'POST',headers:{Authorization:'Bearer '+document.getElementById('token').value},cache:'no-store'});out.textContent=await r.text();}catch(e){out.textContent=e.message;}}document.getElementById('start').onclick=()=>send('/start');document.getElementById('test').onclick=()=>send('/test');</script></html>",{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY'}});
  const names=['Apple','AT&T'];
  const stub=name=>env.MONITORS.get(env.MONITORS.idFromName(name));
  if(['/start','/test'].includes(url.pathname)){
   if(request.method!=='POST'||!env.ADMIN_TOKEN||request.headers.get('Authorization')!==`Bearer ${env.ADMIN_TOKEN}`)return new Response('Unauthorized',{status:401});
   if(url.pathname==='/test')return stub('Apple').fetch(new Request('https://internal/test',{method:'POST'}));
   for(const name of names)await stub(name).fetch(new Request('https://internal'+url.pathname,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({retailer:name})}));
   return Response.json({accepted:true});
  }
  if(url.pathname==='/status')return Response.json(await Promise.all(names.map(async name=>(await stub(name).fetch('https://internal/status')).json())),{headers:{'Cache-Control':'no-store'}});
  if(url.pathname==='/')return new Response('Duo Stock Watch: /status shows current results. Apple nearby target: 30 seconds. Alerts require ntfy configuration.');
  return new Response('Not found',{status:404});
 }
};
