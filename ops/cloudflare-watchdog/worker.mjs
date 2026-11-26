// Independent cron, no HTTP endpoint and no AI inference.
// Deploy only with a fine-grained Actions:write, Contents:read token for this repository.
const API = "https://api.github.com/repos/Ai-luren/AI-Creator-Radar";
const WORKFLOW = "/actions/workflows/update-site.yml";
const COOLDOWN_MS = 12 * 60 * 1000;
const GRACE_MS = 5 * 60 * 1000;
const MAX_AGE_MS = 45 * 60 * 1000;
const MAX_DELAY_MS = 31 * 60 * 1000;

async function request(fetcher, path, token, options={}) {
  const headers = {"Authorization":"Bearer "+token,"User-Agent":"radar-independent-watchdog",
    "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",
    ...(options.headers||{})};
  // Never follow redirects with a credential or accept arbitrary repository/URL input.
  return fetcher(API+path,{...options,headers,redirect:"error"});
}

export async function check(env, now=Date.now(), fetcher=fetch) {
  if (!env.GITHUB_RADAR_TOKEN) throw new Error("Missing GITHUB_RADAR_TOKEN secret");
  const token=env.GITHUB_RADAR_TOKEN;
  const response=await request(fetcher, WORKFLOW+"/runs?branch=main&per_page=10",token);
  if (!response.ok) throw new Error("GitHub run query failed: "+response.status);
  const list=await response.json();
  if (!Array.isArray(list.workflow_runs)) throw new Error("Invalid workflow run payload");
  if(list.workflow_runs.some(r=>r.status!=="completed")) return "active-run";
  const times=list.workflow_runs.map(r=>Date.parse(r.created_at));
  if(times.some(t=>!Number.isFinite(t)||t>now+60000)) throw new Error("Invalid workflow timestamp");
  if(times.length&&now-Math.max(...times)<COOLDOWN_MS) return "cooldown";

  const heartbeat=await request(fetcher,"/contents/site/data/scheduler-health.json?ref=main",token,
     {headers:{"Accept":"application/vnd.github.raw+json"}});
  if(heartbeat.status!==404) {
    if(!heartbeat.ok) throw new Error("Heartbeat query failed: "+heartbeat.status);
    const data=await heartbeat.json();
    const generated=Date.parse(data.generatedAt), due=Date.parse(data.nextDueAt);
    if(data.schema!=="scheduler-health/v1"||!Number.isFinite(generated)||!Number.isFinite(due)||
       generated>now+60000||due<generated||due-generated>MAX_DELAY_MS) {
      throw new Error("Invalid heartbeat; refusing automatic dispatch");
    }
    if(now<due+GRACE_MS&&now-generated<MAX_AGE_MS) return "fresh";
  }
  if(env.DRY_RUN==="true") return "would-dispatch";
  const dispatched=await request(fetcher,WORKFLOW+"/dispatches",token,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({ref:"main",inputs:{scope:"due"}})});
  if(!dispatched.ok) throw new Error("GitHub dispatch failed: "+dispatched.status);
  return "dispatched";
}

export default {
  async scheduled(_event,env,ctx) {
    ctx.waitUntil(check(env).then(result=>console.log("radar watchdog:",result)));
  }
};
