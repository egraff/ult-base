Param(
    [Parameter(Mandatory=$true)]
    [int]
    $TestResult
)

$ErrorActionPreference = "Stop"

if ($env:APPVEYOR_PULL_REQUEST_NUMBER) {
    # Likely a pull request from a forked repository.
    # Committing the test results can only be done when secure environment
    # variables are available.
    exit 0
}

$ErrorActionPreference = "Continue"
ssh -o StrictHostKeyChecking=no -T git@github.com 2>&1 | %{ "$_" }

$ErrorActionPreference = "Stop"

# Make sure we're in the top directory
cd $env:APPVEYOR_BUILD_FOLDER

Write-Host "Creating temporary directory"
$GhPages = md (Join-Path ([System.IO.Path]::GetTempPath()) ([string][System.Guid]::NewGuid())) -Force | %{ $_.FullName }


Push-Location -Path $GhPages

git init
git config core.autocrlf true
git config user.name "AppVeyor"
git config user.email "appveyor@appveyor.com"
git config remote.origin.url git@github.com:egraff/ult-base.git
git config remote.origin.fetch +refs/heads/gh-pages:refs/remotes/origin/gh-pages
git config branch.gh-pages.remote origin
git config branch.gh-pages.merge refs/heads/gh-pages

git fetch
git checkout -l -f -q -b gh-pages origin/gh-pages

Pop-Location


$JobDir = md "$GhPages\appveyor-builds\${env:APPVEYOR_JOB_NUMBER}" | %{ $_.FullName }

@"
---
layout: test-result
appveyor:
  branch: ${env:APPVEYOR_REPO_BRANCH}
  build-id: ${env:APPVEYOR_BUILD_ID}
  build-number: ${env:APPVEYOR_BUILD_NUMBER}
  commit: ${env:APPVEYOR_REPO_COMMIT}
  job-id: ${env:APPVEYOR_JOB_ID}
  job-number: ${env:APPVEYOR_JOB_NUMBER}
  os-name: Windows
  test-result: $TestResult
---
"@ | Set-Content -Path "$JobDir\index.md"

# XXX: DEBUG
Get-Content -Path "$JobDir\index.md" | Out-String


cp -Rf test\.build "$JobDir\build" -Recurse -ErrorAction Ignore
cp -Rf test\diffs "$JobDir\diffs" -Recurse -ErrorAction Ignore
cp -Rf test\tmp\tests "$JobDir\tests" -Recurse -ErrorAction Ignore
cp -Rf test\tmp\proto "$JobDir\proto" -Recurse -ErrorAction Ignore

md "$GhPages\_data\appveyor-builds" -Force
cp test\test_result.json "$GhPages\_data\appveyor-builds\$($env:APPVEYOR_JOB_NUMBER -replace '.','_').json"


Push-Location -Path $GhPages

git add --all .
git commit -m "AppVeyor: test results from job ${env:APPVEYOR_JOB_NUMBER}"



Pop-Location
