// Deploy the exact artifact ID already validated by wait_pages_artifact.sh.
// GitHub Pages REST API; avoid a second, eventually consistent name lookup.
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const terminal = new Set(['deployment_failed','deployment_content_failed','deployment_cancelled','deployment_lost']);
async function deploy({github, context, core, artifactId, wait=sleep, polls=48}) {
  if (!/^\d+$/.test(String(artifactId)) || !Number.isSafeInteger(Number(artifactId)) || Number(artifactId)<=0)
    throw new Error('Invalid verified Pages artifact ID');
  const repo = context.repo;
  let created;
  // Exactly one write. An ambiguous response is not a license to create twice.
  try {
    const oidc = await core.getIDToken();
    core.setSecret(oidc);
    created = (await github.request('POST /repos/{owner}/{repo}/pages/deployments', {
      ...repo, artifact_id: Number(artifactId), pages_build_version: context.sha, oidc_token: oidc
    })).data;
  } catch (error) {
    // Never print request objects which might contain an OIDC token.
    throw new Error('Pages creation failed or ambiguous (HTTP '+(Number(error.status)||'unknown')+'); next scheduler will reconcile publication.');
  }
  const id = created?.id || String(created?.status_url||'').match(/\/deployments\/([^/]+)\/status$/)?.[1];
  if (!id || !/^[A-Za-z0-9_-]+$/.test(String(id))) throw new Error('Pages did not return a valid deployment ID');
  for (let i=0;i<polls;i++) {
    await wait(10000);
    let state;
    try {
      state=(await github.request('GET /repos/{owner}/{repo}/pages/deployments/{pages_deployment_id}', {...repo,pages_deployment_id:id})).data?.status;
    } catch(error) {
      const status=Number(error.status)||0;
      if(status && ![404,408,429].includes(status) && status<500) throw new Error('Pages status request failed (HTTP '+status+')');
      continue;
    }
    if(state==='succeed'){core.setOutput('page_url',created.page_url||'');return id;}
    if(terminal.has(state))throw new Error('Pages deployment ended: '+state);
  }
  // Preserve failure truth; don't issue another write or cancel a potentially completed deployment.
  throw new Error('Pages deployment status not confirmed within bounded polling');
}
module.exports=deploy;
