/** Notify only this reviewed release's changed URLs after production verification. */
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const config=JSON.parse(fs.readFileSync(path.join(root,'indexnow-config.json'),'utf8'));
const review=JSON.parse(fs.readFileSync(path.join(root,'seo-geo-review.json'),'utf8'));
const urlList=Object.keys(review.pages).map(file=>'https://'+config.host+'/'+file.replace(/index\.html$/,'')).map(url=>new URL(url).href);
if(urlList.length>10000||new Set(urlList).size!==urlList.length)throw Error('Invalid changed URL batch');
const commit=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim();
const committed=new Set(execFileSync('git',['diff','--no-renames','--name-only','-z','HEAD^','HEAD'],{cwd:root,encoding:'utf8'}).split('\0').filter(Boolean));
const send=process.argv.includes('--send');const receiptArg=process.argv.find(a=>a.startsWith('--receipt='));
if(!send){console.log(JSON.stringify({mode:'dry-run',commit,urls:urlList.length,endpoint:config.endpoint,indexingGuaranteed:false}));process.exit(0)}
if(!receiptArg)throw Error('Use an external receipt path to prevent repeat notification');
if(!committed.has('seo-geo-review.json')||Object.keys(review.pages).some(file=>!committed.has(file)))throw Error('The notification list is not the changed-page list of this commit');
const receipt=path.resolve(receiptArg.slice('--receipt='.length));
if(receipt.startsWith(root+path.sep))throw Error('Receipt must be outside the checkout');
if(fs.existsSync(receipt))throw Error('Receipt already exists; inspect the previous outcome rather than submitting again');
// Require a successful domain/commit check by the release verifier, not just a local Git commit.
const verified=JSON.parse(fs.readFileSync(path.join(path.dirname(receipt),'release-info.json'),'utf8'));
if(verified.commit!==commit||verified.readyState!=='READY'||verified.domain!=='https://'+config.host+'/')throw Error('Production release has not been verified for this commit');
const keyResponse=await fetch(config.keyLocation);
if(!keyResponse.ok||(await keyResponse.text()).trim()!==config.key)throw Error('Public ownership proof is unavailable');
const prepared={commit,urls:urlList.length,state:'sending',preparedAt:new Date().toISOString(),indexingGuaranteed:false};
fs.writeFileSync(receipt,JSON.stringify(prepared,null,2));
try{
 const response=await fetch(config.endpoint,{method:'POST',headers:{'Content-Type':'application/json; charset=utf-8'},body:JSON.stringify({host:config.host,key:config.key,keyLocation:config.keyLocation,urlList})});
 const result={...prepared,state:'received',status:response.status,response:(await response.text()).slice(0,1000),finishedAt:new Date().toISOString()};
 fs.writeFileSync(receipt,JSON.stringify(result,null,2));console.log(JSON.stringify({commit,urls:urlList.length,status:response.status,indexingGuaranteed:false}));
 if(![200,202].includes(response.status))process.exitCode=1;
}catch(error){fs.writeFileSync(receipt,JSON.stringify({...prepared,state:'uncertain',error:String(error)},null,2));throw error}
