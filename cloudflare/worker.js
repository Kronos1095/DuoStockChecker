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
   await this.state.storage.put('test',{created:Date.now(),notBefore:Date.now()+20000,message:'TEST: confirm this reaches your locked iPad promptly.'});
   await this.state.storage.setAlarm(Date.now()+20000);return Response.json({testQueued:true});
  }
  return Response.json(await this.state.storage.get('status')||{health:'not_started'});
 }
 async push(title,message,link){
  if(!this.env.NTFY_TOPIC)throw Error('NTFY_TOPIC missing');
  const headers={'Content-Type':'application/json'};if(this.env.NTFY_TOKEN)headers.Authorization=`Bearer ${this.env.NTFY_TOKEN}`;
  const response=await fetch('https://ntfy.sh',{method:'POST',headers,body:JSON.stringify({topic:this.env.NTFY_TOPIC,title,message,priority:5,tags:['iphone','rotating_light'],click:link}),signal:AbortSignal.timeout(8000)});
  if(!response.ok)throw Error('Push server rejected message');
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
   status={retailer,health:searches.some(s=>s.status==='unknown')?'partial':'ok',updated:new Date(now).toISOString(),message,stores,searches,notificationsConfigured:!!this.env.NTFY_TOPIC};
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
  if(url.pathname==='/setup')return new Response("<!doctype html><html><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Duo Stock Watch controls</title><style>body{font:18px system-ui;max-width:650px;margin:30px auto;padding:20px;background:#101827;color:#fff}input,button{font:inherit;padding:14px;margin:10px 0;box-sizing:border-box;width:100%}pre{white-space:pre-wrap;font-size:14px}a{color:#aecbff}</style><h1>Duo Stock Watch</h1><p>Enter the ADMIN_TOKEN you saved in Cloudflare. It stays in this page's memory and is sent only to this Worker's protected controls.</p><input type=\"password\" id=\"token\" autocomplete=\"off\" placeholder=\"ADMIN_TOKEN\"><button id=\"start\">Start Apple and AT&T checks</button><button id=\"test\">Send test in about 20 seconds</button><p>After requesting the test, lock your iPad. Confirm the notification appears with sound. Push-server acceptance does not confirm device delivery.</p><a href=\"/status\">View current status</a><pre id=\"result\"></pre><script>async function send(path){const out=document.getElementById('result');out.textContent='Sending…';try{const r=await fetch(path,{method:'POST',headers:{Authorization:'Bearer '+document.getElementById('token').value},cache:'no-store'});out.textContent=await r.text();if(r.ok&&path==='/test')out.textContent+='\\nLock your iPad now; test queued for approximately 20 seconds.';}catch(e){out.textContent=e.message;}}document.getElementById('start').onclick=()=>send('/start');document.getElementById('test').onclick=()=>send('/test');</script></html>",{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY'}});
  const names=['Apple','AT&T'];
  const stub=name=>env.MONITORS.get(env.MONITORS.idFromName(name));
  if(['/start','/test'].includes(url.pathname)){
   if(request.method!=='POST'||!env.ADMIN_TOKEN||request.headers.get('Authorization')!==`Bearer ${env.ADMIN_TOKEN}`)return new Response('Unauthorized',{status:401});
   for(const name of url.pathname==='/test'?['Apple']:names)await stub(name).fetch(new Request('https://internal'+url.pathname,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({retailer:name})}));
   return Response.json({accepted:true});
  }
  if(url.pathname==='/status')return Response.json(await Promise.all(names.map(async name=>(await stub(name).fetch('https://internal/status')).json())),{headers:{'Cache-Control':'no-store'}});
  if(url.pathname==='/')return new Response('Duo Stock Watch: /status shows current results. Apple nearby target: 30 seconds. Alerts require ntfy configuration.');
  return new Response('Not found',{status:404});
 }
};
