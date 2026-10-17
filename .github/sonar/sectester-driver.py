"""Independent scan target; token stays inside the existing Actions repository."""
import os,pathlib,sys,time,json,urllib.request
helper=pathlib.Path(__file__).with_name('report.py').read_text(encoding='utf-8')
exec(compile(helper.split('\ntry:\n    if MODE ==')[0],__file__,'exec'))
TARGET='dbalikhin/sectester-net-demo'
try:
    if MODE=='automatic':
        try:api('components/show',{'component':PROJECT})
        except RuntimeError as e:
            if 'HTTP 404' not in str(e):raise
            save('provision.json',api('alm_integration/provision_projects',{'organization':ORG,'installationKeys':TARGET+'|1422891019'},post=True))
        configure(True)
        baseline=os.environ['TARGET_SOURCE_SHA']
        print('READY_FOR_TRIGGER: waiting for metadata-only commit on '+TARGET,flush=True)
        start=time.monotonic()
        while time.monotonic()-start<1200:
            analyses=api('project_analyses/search',{'project':PROJECT,'ps':20})['analyses']
            initial=next((a for a in analyses if a.get('revision')==baseline),None)
            if initial:
                # Preserve the actual import record, rather than wait indefinitely
                # for a webhook. Do not claim it used the later configured profile.
                commit=baseline;analysis=initial
                save('automatic-provenance.json',{'trigger':'initial project import','profile_parity_verified':False,'later_metadata_trigger_produced_analysis':False,'coverage_note':'No C# measured in initial record; not a successful all-rules C# scan.'})
                break
            with urllib.request.urlopen('https://api.github.com/repos/'+TARGET+'/commits/master',timeout=60) as response:commit=json.load(response)['sha']
            if commit!=baseline:
                analyses=api('project_analyses/search',{'project':PROJECT,'ps':20})['analyses']
                analysis=next((a for a in analyses if a.get('revision')==commit),None)
                if analysis:break
            time.sleep(15)
        else:raise RuntimeError('Automatic analysis timed out; coverage remains unverified.')
        subprocess.check_call(['git','fetch','origin',commit]);subprocess.check_call(['git','checkout','--detach',commit])
        before=json.loads((OUTPUT/'source-manifest.json').read_text(encoding='utf-8'))
        after={n:hashlib.sha256(pathlib.Path(n).read_bytes()).hexdigest() for n in before}
        if before!=after:raise RuntimeError('Application source changed.')
        with open(os.environ['GITHUB_ENV'],'a',encoding='utf-8') as stream:stream.write('COMPARISON_COMMIT='+commit+'\n')
        export({'analysis':analysis,'method':'Cloud Automatic Analysis; no user build'},commit,{'automatic_wall_seconds':time.monotonic()-start})
    elif MODE=='preflight':
        configure(False)
        before=json.loads(pathlib.Path('sonar-artifacts/automatic/source-manifest.json').read_text(encoding='utf-8'))
        after=json.loads((OUTPUT/'source-manifest.json').read_text(encoding='utf-8'))
        if before!=after:raise RuntimeError('Source differs across modes.')
    elif MODE=='collect':
        # Reuse the original collector with identical environment and current checkout.
        exec(compile(helper[helper.index('\ntry:\n    if MODE =='):],__file__,'exec'))
    else:raise RuntimeError('Unexpected mode.')
except Exception as error:
    save('error.json',{'mode':MODE,'error':str(error).replace(TOKEN,'[redacted]')})
    print(str(error).replace(TOKEN,'[redacted]'),file=sys.stderr);sys.exit(1)
