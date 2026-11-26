import test from "node:test";
import assert from "node:assert/strict";
import {check} from "../ops/cloudflare-watchdog/worker.mjs";
const now=Date.parse("2026-11-26T18:30:00Z");
const env={GITHUB_RADAR_TOKEN:"test-token",DRY_RUN:"false"};
function mock({runs=[],manifest,code=200,dispatchCode=204}={}) {
  const calls=[];
  const fetcher=async (url,options)=>{
    calls.push({url,options});
    if(url.includes("/runs?")) return Response.json({workflow_runs:runs});
    if(url.includes("/contents/")) return code===200?Response.json(manifest):new Response(null,{status:code});
    return new Response(null,{status:dispatchCode});
  };
  return {calls,fetcher};
}
const heartbeat=(age,due)=>({schema:"scheduler-health/v1",generatedAt:new Date(now-age*60000).toISOString(),
  nextDueAt:new Date(now+due*60000).toISOString()});
test("fresh heartbeat skips dispatch",async()=>{
 const m=mock({manifest:heartbeat(10,15)});
 assert.equal(await check(env,now,m.fetcher),"fresh");assert.equal(m.calls.length,2);
});
test("active and very recent runs suppress duplicates",async()=>{
 for(const [status,age,expected] of [["in_progress",30,"active-run"],["completed",5,"cooldown"]]){
 const m=mock({runs:[{status,created_at:new Date(now-age*60000).toISOString()}]});
 assert.equal(await check(env,now,m.fetcher),expected);assert.equal(m.calls.length,1);
 }
});
test("overdue heartbeat dispatches only due scope to main",async()=>{
 const m=mock({manifest:heartbeat(60,-35)});
 assert.equal(await check(env,now,m.fetcher),"dispatched");
 assert.equal(m.calls.length,3);
 assert.deepEqual(JSON.parse(m.calls[2].options.body),{ref:"main",inputs:{scope:"due"}});
 assert.equal(m.calls[2].options.redirect,"error");
});
test("dry run and first bootstrap do not write without authorization flag",async()=>{
 const m=mock({code:404});
 assert.equal(await check({...env,DRY_RUN:"true"},now,m.fetcher),"would-dispatch");
 assert.equal(m.calls.length,2);
});
test("API errors and malformed heartbeat fail closed",async()=>{
 for(const options of [{code:403},{manifest:{schema:"bad"}},{manifest:heartbeat(1,70)}]){
 const m=mock(options);await assert.rejects(check(env,now,m.fetcher));assert.equal(m.calls.length,2);
 }
});
test("dispatch failure is not reported as success",async()=>{
 const m=mock({manifest:heartbeat(60,-35),dispatchCode:403});
 await assert.rejects(check(env,now,m.fetcher),/403/);
});
test("missing secret prevents all requests",async()=>{
 const m=mock();await assert.rejects(check({},now,m.fetcher),/Missing/);assert.equal(m.calls.length,0);
});
