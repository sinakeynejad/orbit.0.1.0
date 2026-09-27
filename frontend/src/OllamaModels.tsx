import {useEffect, useState} from 'react';

type Props = {baseUrl:string; value:string; onSelect:(name:string)=>void};
export function OllamaModels({baseUrl,value,onSelect}:Props) {
 const [models,setModels]=useState<string[]>([]);
 const [loading,setLoading]=useState(true),[error,setError]=useState(''),[revision,setRevision]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();
  setModels([]);setLoading(true);setError('');
  // Debounce URL edits and ignore responses from previous endpoints or closed settings.
  const timer=setTimeout(async()=>{
   try {
    const response=await fetch('/settings/ollama-models',{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({llm_base_url:baseUrl})});
    const data=await response.json();
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Unable to load models. Please retry.');
    if(!controller.signal.aborted)setModels(data.models);
   } catch(e) {if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Unable to load models. Please retry.');}
   finally {if(!controller.signal.aborted)setLoading(false);}
  },350);
  return()=>{clearTimeout(timer);controller.abort();};
 },[baseUrl,revision]);
 return <div className="model-picker">
  <label>Installed Ollama models<select aria-label="Installed Ollama models" disabled={loading||models.length===0} value={models.includes(value)?value:''} onChange={e=>{if(e.target.value)onSelect(e.target.value);}}>
   <option value="">{loading?'Loading models…':'Choose an installed model'}</option>
   {models.map(name=><option key={name} value={name}>{name}</option>)}
  </select></label>
  <button onClick={()=>setRevision(n=>n+1)} disabled={loading}>Refresh models</button>
  <p role="status">{loading?'Checking your Ollama server…':error||(!models.length?'No models installed on this server. Install a model in Ollama, then refresh.':`${models.length} installed model${models.length===1?'':'s'}. Choose one, then save settings.`)}</p>
  {!loading&&!error&&models.length>0&&value&&!models.includes(value)&&<small>Your current model is not in this list. You can select another or keep the name entered below.</small>}
 </div>;
}
