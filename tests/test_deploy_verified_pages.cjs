const test = require('node:test');
const assert = require('node:assert/strict');
const deploy = require('../scripts/deploy_verified_pages.cjs');
function fixture(states) {
 const calls=[],outputs=[];
 const core={getIDToken:async()=> 'fixture-token',setSecret(){},setOutput:(k,v)=>outputs.push([k,v])};
 const github={request:async(route,args)=>{
  calls.push([route,args]);
  if(route.startsWith('POST'))return {data:{id:'deployment-1',page_url:'https://example.test/'}};
  const next=states.shift();if(next instanceof Error)throw next;
  return {data:{status:next}};
 }};
 return {calls,outputs,opts:{github,core,context:{repo:{owner:'o',repo:'r'},sha:'sha'},artifactId:'123',wait:async()=>{},polls:4}};
}
test('verified artifact ID used directly; transient status lookup retries only reads',async()=>{
 const f=fixture([Object.assign(new Error('temporary'),{status:503}),'deployment_attempt_error','succeed']);
 await deploy(f.opts);
 assert.equal(f.calls.filter(c=>c[0].startsWith('POST')).length,1);
 assert.equal(f.calls[0][1].artifact_id,123);
 assert.deepEqual(f.outputs,[['page_url','https://example.test/']]);
 assert.ok(f.calls.every(c=>!c[0].includes('/artifacts')));
});
test('invalid ID and ambiguous creation never trigger duplicate writes or expose token',async()=>{
 const f=fixture([]);await assert.rejects(deploy({...f.opts,artifactId:'bad'}),/Invalid/);assert.equal(f.calls.length,0);
 let attempts=0;f.opts.github.request=async()=>{attempts++;throw new Error('fixture-token')};
 await assert.rejects(deploy(f.opts),e=>/ambiguous/.test(e.message)&&!e.message.includes('fixture-token'));
 assert.equal(attempts,1);
});
test('terminal failure and polling timeout are not success',async()=>{
 const f=fixture(['deployment_content_failed']);await assert.rejects(deploy(f.opts),/deployment_content_failed/);assert.equal(f.outputs.length,0);
 const g=fixture(['pending','pending','pending','pending']);await assert.rejects(deploy(g.opts),/not confirmed/);assert.equal(g.calls.filter(c=>c[0].startsWith('POST')).length,1);
});
