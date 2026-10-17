"""Observe a metadata-triggered Cloud scan, preserving baseline and source identity."""
import os,pathlib,sys,time,json,urllib.request,base64,datetime
phase=sys.argv[1]
sys.argv[1]='automatic'
helper=pathlib.Path(__file__).with_name('report.py').read_text(encoding='utf-8')
exec(compile(helper.split('\ntry:\n    if MODE ==')[0],__file__,'exec'))
REPO=os.environ['TARGET_REPO'];BRANCH=os.environ['TARGET_BRANCH'];BASE=os.environ['TARGET_SOURCE_SHA']

def public(path):
    request=urllib.request.Request('https://api.github.com/repos/dbalikhin/'+REPO+'/'+path,headers={'Accept':'application/vnd.github+json','User-Agent':'sonar-automatic-comparison'})
    with urllib.request.urlopen(request,timeout=60) as response:return json.load(response)

def manifest():
    names=subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
    return {n:hashlib.sha256(pathlib.Path(n).read_bytes()).hexdigest() for n in names if pathlib.Path(n).suffix.lower() in {'.cs','.cshtml','.razor','.csproj','.props','.targets','.sln','.slnx'}}

try:
    if phase=='prepare':
        save('previous-analyses.json',api('project_analyses/search',{'project':PROJECT,'ps':20}))
        save('previous-csharp-issues.json',pages('issues/search',{'componentKeys':PROJECT,'languages':'cs','resolved':'false'},'issues'))
        save('previous-hotspots.json',pages('hotspots/search',{'projectKey':PROJECT},'hotspots'))
        configure(True)
        save('readiness.json',{'repository':'dbalikhin/'+REPO,'branch':BRANCH,'baseline_commit':BASE,'run_id':os.environ['GITHUB_RUN_ID'],'project':PROJECT,'state':'ready_for_metadata_trigger','prepared_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
        print('Ready: '+REPO,flush=True)
    elif phase=='observe':
        start=time.monotonic();candidate=None
        while time.monotonic()-start<2700:
            head=public('commits/'+urllib.parse.quote(BRANCH,safe=''))
            revision=head['sha']
            if revision!=BASE:
                marker=public('contents/.github/sonar/automatic-trigger.json?ref='+revision)
                content=json.loads(base64.b64decode(marker['content']))
                if str(content.get('run'))==os.environ['GITHUB_RUN_ID']:
                    candidate=revision
                    analyses=api('project_analyses/search',{'project':PROJECT,'ps':20})['analyses']
                    if analyses and analyses[0].get('revision')==candidate:
                        analysis=analyses[0];break
            time.sleep(15)
        else:raise RuntimeError('Timed out waiting for this run metadata commit to be analyzed; coverage remains unverified.')
        subprocess.check_call(['git','fetch','origin',candidate]);subprocess.check_call(['git','checkout','--detach',candidate])
        before=json.loads((OUTPUT/'source-manifest.json').read_text(encoding='utf-8'))
        after=manifest()
        save('source-verification.json',{'baseline_commit':BASE,'analyzed_commit':candidate,'file_count':len(before),'identical_source_and_build_files':before==after,'analysis':analysis})
        if before!=after:raise RuntimeError('Application source/build files changed; refusing source-equivalent comparison.')
        task_data=api('ce/activity',{'component':PROJECT,'ps':30})
        task=next((t for t in task_data.get('tasks',[]) if t.get('analysisId')==analysis['key']),None)
        trigger_date=head['commit']['committer']['date']
        trigger_time=datetime.datetime.fromisoformat(trigger_date.replace('Z','+00:00'))
        observed=datetime.datetime.now(datetime.timezone.utc)
        timing={'metadata_commit_to_observation_seconds':(observed-trigger_time).total_seconds(),'observation_wait_seconds':time.monotonic()-start,'scanner_wall_seconds':None,'server_execution_seconds':task.get('executionTimeMs',0)/1000 if task else None,'timing_note':'Commit-to-observation includes queue, hosted scanning, server processing, indexing and polling. Cloud scanner runtime is not separately exposed.'}
        save('trigger.json',{'commit':candidate,'baseline_commit':BASE,'triggered_at':trigger_date,'observed_at':observed.isoformat(),'run':os.environ['GITHUB_RUN_ID']})
        export({'analysis':analysis,'method':'SonarQube Cloud Automatic Analysis; no user build','compute_task':task},candidate,timing)
        latest=api('project_analyses/search',{'project':PROJECT,'ps':1})['analyses'][0]
        if latest['key']!=analysis['key']:raise RuntimeError('Project analysis changed during export; snapshot consistency unverified.')
        summary=json.loads((OUTPUT/'summary.json').read_text(encoding='utf-8'))
        if summary['csharp_ncloc']==0:raise RuntimeError('Automatic scan completed but measured zero C# LOC; incomplete coverage.')
    else:raise RuntimeError('Expected prepare or observe.')
except Exception as error:
    save('error.json',{'phase':phase,'repository':REPO,'error':str(error).replace(TOKEN,'[redacted]')})
    print(str(error).replace(TOKEN,'[redacted]'),file=sys.stderr);sys.exit(1)
