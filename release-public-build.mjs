/** Reproduce only the reviewed public snapshot. No authoring files are served. */
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const output=path.join(root,'.public-release');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'release-public-manifest.json'),'utf8'));
const files=Object.entries(manifest.files);
const selected=new Set(files.map(([name])=>name));
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
function reviewedBytes(bytes,hash,name) {
  if(digest(bytes)===hash)return true;
  // Git converts working-tree CRLF to LF on Linux. Accept only that reversible
  // text-file representation change; binary assets still require exact bytes.
  if(!/\.(?:html|css|js|json|xml|txt|svg|webmanifest)$/i.test(name))return false;
  const lf=bytes.toString('utf8').replaceAll('\r\n','\n');
  if(manifest.textSha256?.[name] && digest(Buffer.from(lf))===manifest.textSha256[name])return true;
  return digest(Buffer.from(lf))===hash||digest(Buffer.from(lf.replaceAll('\n','\r\n')))===hash;
}
const existingDirectories=new Set();
if(fs.existsSync(output)) {
  if((await fs.promises.lstat(output)).isSymbolicLink())throw Error('Output symlink is not allowed');
  // Preserve the full output allow-list check without serial directory I/O.
  const pending=[output];
  while(pending.length){
    const batch=pending.splice(0,24);
    await Promise.all(batch.map(async dir=>{
      const entries=await fs.promises.readdir(dir,{withFileTypes:true});
      existingDirectories.add(dir);
      for(const entry of entries){
        if(entry.isSymbolicLink())throw Error('Output symlink is not allowed');
        const full=path.join(dir,entry.name);
        if(entry.isDirectory())pending.push(full);
        else if(!selected.has(path.relative(output,full).replaceAll('\\','/')))throw Error('Unexpected existing output '+full);
      }
    }));
  }
}
const makingDirectories=new Map();
async function ensureDirectory(dir){
  if(existingDirectories.has(dir))return;
  if(!makingDirectories.has(dir))makingDirectories.set(dir,fs.promises.mkdir(dir,{recursive:true}).then(()=>existingDirectories.add(dir)));
  await makingDirectories.get(dir);
}
let cursor=0,copied=0;
await Promise.all(Array.from({length:12},async()=>{
  while(cursor<files.length){
    const [name,hash]=files[cursor++];
    const input=path.resolve(root,name),dest=path.resolve(output,name);
    if(!input.startsWith(root+path.sep)||!dest.startsWith(output+path.sep)||name.split('/').some(p=>p.startsWith('.')))throw Error('Unsafe public path '+name);
    if((await fs.promises.lstat(input)).isSymbolicLink())throw Error('Source symlink '+name);
    const bytes=await fs.promises.readFile(input);
    if(!reviewedBytes(bytes,hash,name))throw Error('Reviewed file changed; refresh release manifest: '+name);
    await ensureDirectory(path.dirname(dest));
    await fs.promises.writeFile(dest,bytes);
    if(++copied%2000===0)console.log(JSON.stringify({copied,total:files.length}));
  }
}));
console.log(JSON.stringify({publicFiles:files.length,sitemapPages:manifest.sitemapPages,output:'.public-release',privateSourcesIncluded:false}));
