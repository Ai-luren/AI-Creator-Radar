import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';

const file=fileURLToPath(new URL('../site/creator-intel.js',import.meta.url));
const script=fs.readFileSync(file,'utf8');
const now=Date.parse('2026-11-28T12:00:00Z');
const ctx=vm.createContext({document:{addEventListener(){}},URL,Date,Map,Set});
vm.runInContext(script,ctx);
const row={source:'revid',verification:'provider-reported',url:'https://x.com/i/web/status/123',platform:'x',postedAt:'2026-11-27T12:00:00Z',observedAt:'2026-11-28T10:00:00Z',views:30000,likes:null,shares:0,creativeTopics:['cinematic']};
test('personal display rejects stale, invalid URL, mismatched platform and invalid metrics',()=>{
 const raw={candidates:[row,row,{...row,url:'https://example.com/video'},{...row,url:'https://x.com/i/web/status/124',platform:'youtube'},{...row,url:'https://x.com/i/web/status/125',postedAt:'2026-11-01T00:00:00Z'},{...row,url:'https://x.com/i/web/status/126',views:'30000'},{...row,url:'https://x.com/i/web/status/127',creativeTopics:['constructor']}]};
 const result=ctx.revidPersonalRows(JSON.stringify(raw),now);
 assert.equal(result.length,1);
 assert.equal(result[0].likes,null);
 assert.equal(result[0].shares,0);
 assert.equal(result[0].views,30000);
 assert.equal(result[0].topics[0],'cinematic');
 assert.throws(()=>ctx.revidPersonalRows('bad',now));
});
