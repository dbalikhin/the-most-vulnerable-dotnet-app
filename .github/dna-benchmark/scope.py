import pathlib,subprocess,json,os
if os.environ['TARGET_REPO']=='Remotely':
    excluded=['Desktop.Core/Desktop.Core.csproj','Tests/Desktop.Win.Tests/Desktop.Win.Tests.csproj']
    paths=[p for p in subprocess.check_output(['git','ls-files','*.csproj'],text=True).splitlines() if p not in excluded]
    pathlib.Path('Benchmark.slnx').write_text('<Solution>'+''.join('<Project Path="'+p+'" />' for p in paths)+'</Solution>',encoding='utf-8')
    pathlib.Path('benchmark-evidence').mkdir(exist_ok=True)
    pathlib.Path('benchmark-evidence/build-scope.json').write_text(json.dumps(dict(included=paths,extra_projects=excluded,excluded_non_csharp=['docker-compose/docker-compose.dcproj']),indent=2))
