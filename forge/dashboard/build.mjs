// Dependencies/build products stay isolated. Runtime uses only checked-in local assets.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';

const root=path.dirname(fileURLToPath(import.meta.url));
const manifest=await fs.readFile(path.join(root,'package.json'));
const lock=await fs.readFile(path.join(root,'package-lock.json'));
const cache=path.join(os.tmpdir(),'idea-foundry-dashboard-'+crypto.createHash('sha256').update(lock).digest('hex').slice(0,16));
await fs.mkdir(cache,{recursive:true});
await fs.writeFile(path.join(cache,'package.json'),manifest);
await fs.writeFile(path.join(cache,'package-lock.json'),lock);
const modules=path.join(cache,'node_modules');
try {await fs.access(path.join(modules,'typescript/lib/tsc.js'));}
catch {
  const installed=spawnSync(process.platform==='win32'?'npm.cmd':'npm',['ci','--ignore-scripts','--no-audit','--no-fund','--cache',path.join(cache,'npm-cache')],{cwd:cache,stdio:'inherit',shell:process.platform==='win32'});
  if(installed.status!==0)process.exit(installed.status||1);
}
if(process.argv[2]==='typecheck') {
  const config=JSON.parse(await fs.readFile(path.join(root,'tsconfig.json'),'utf8'));
  config.include=[path.join(root,'src')];
  config.compilerOptions.baseUrl=root;
  config.compilerOptions.typeRoots=[path.join(modules,'@types')];
  config.compilerOptions.paths={
    react:[path.join(modules,'@types/react/index.d.ts')],
    'react/jsx-runtime':[path.join(modules,'@types/react/jsx-runtime.d.ts')],
    'react-dom/client':[path.join(modules,'@types/react-dom/client.d.ts')],
    '@xyflow/react':[path.join(modules,'@xyflow/react/dist/esm/index.d.ts')],
    'elkjs/*':[path.join(modules,'elkjs/*')]
  };
  const file=path.join(cache,'tsconfig.foundry.json');await fs.writeFile(file,JSON.stringify(config));
  const result=spawnSync(process.execPath,[path.join(modules,'typescript/lib/tsc.js'),'-p',file],{stdio:'inherit'});
  process.exit(result.status||0);
}
const {build}=await import(pathToFileURL(path.join(modules,'esbuild/lib/main.js')).href);
const assets=path.join(root,'assets');await fs.mkdir(assets,{recursive:true});
await build({entryPoints:[path.join(root,'src/App.tsx')],outfile:path.join(assets,'app.js'),bundle:true,minify:true,format:'esm',target:'es2022',nodePaths:[modules],legalComments:'external',external:['web-worker'],define:{'process.env.NODE_ENV':'"production"'}});
const vendor=await fs.readFile(path.join(modules,'@xyflow/react/dist/style.css'),'utf8');
const own=await fs.readFile(path.join(root,'src/styles.css'),'utf8');
await fs.writeFile(path.join(assets,'app.css'),'@scope (.ifd-shell) {\n'+vendor+'\n}\n'+own);
const worker=await fs.readFile(path.join(modules,'elkjs/lib/elk-worker.min.js'),'utf8');
const cleanLines=text=>text.split(/\r?\n/).map(line=>line.trimEnd()).join('\n').trimEnd()+'\n';
await fs.writeFile(path.join(assets,'elk-worker.js'),cleanLines(worker));
const notices=[];
async function licenses(directory) {
  for(const entry of await fs.readdir(directory,{withFileTypes:true})) {
    if(!entry.isDirectory()||entry.name.startsWith('.'))continue;
    const folder=path.join(directory,entry.name);
    if(entry.name.startsWith('@')){await licenses(folder);continue;}
    try {
      const pkg=JSON.parse(await fs.readFile(path.join(folder,'package.json'),'utf8'));
      for(const name of await fs.readdir(folder))if(/^(license|copying|notice)(\.|$)/i.test(name)) {
        const text=await fs.readFile(path.join(folder,name),'utf8');
        notices.push(`\n=== ${pkg.name}@${pkg.version} — ${name} ===\n${text}`);
      }
    }catch{ /* A directory without package metadata is not a distributed module. */ }
  }
}
await licenses(modules);
await fs.writeFile(path.join(root,'THIRD_PARTY_NOTICES.txt'),cleanLines(notices.join('\n')));
console.log('Built local dashboard assets. Dependencies remain in the OS temporary build cache.');
