#!/usr/bin/env bash

# Exit on failure, verbose
set -ev

if [[ ! -z "$CIRCLE_PULL_REQUEST" ]]; then
  # Likely a pull request from a forked repository.
  # Committing the test results can only be done when secure environment
  # variables are available.
  echo "Insecure environment, test result will not be persisted..."
  exit 0
fi

# Make sure we're in the top directory
cd "${CIRCLE_WORKING_DIRECTORY/#\~/$HOME}"

# Create a new temp directory for committing test results to gh-pages branch
GH_PAGES=$(mktemp -d)
JOB_DIR=${GH_PAGES}/circleci-builds/${CIRCLE_PIPELINE_NUMBER}.${CIRCLE_BUILD_NUM}
mkdir -p $JOB_DIR


pushd $GH_PAGES

git init
git config core.autocrlf true
git config user.name "CircleCI"
git config user.email "circleci@circleci.com"
git config remote.origin.url git@github.com:egraff/ult-base.git
git config remote.origin.fetch +refs/heads/gh-pages:refs/remotes/origin/gh-pages
git config branch.gh-pages.remote origin
git config branch.gh-pages.merge refs/heads/gh-pages

git fetch
git checkout -l -f -q -b gh-pages origin/gh-pages

popd


cat <<EOF > $JOB_DIR/index.md
---
layout: circleci-build
circleci:
  branch: ${CIRCLE_BRANCH}
  build-id: ${CIRCLE_WORKFLOW_ID}
  build-number: ${CIRCLE_PIPELINE_NUMBER}
  commit: ${CIRCLE_SHA1}
  job-id: ${CIRCLE_WORKFLOW_JOB_ID}
  job-number: ${CIRCLE_BUILD_NUM}
  os-name: Ubuntu
  test-result: $1
---
EOF

rsync --archive test/.build/ $JOB_DIR/build/
rsync --archive test/diffs/ $JOB_DIR/diffs/ || true
rsync --archive test/tmp/tests/ $JOB_DIR/tests/ || true
rsync --archive test/tmp/proto/ $JOB_DIR/proto/ || true

mkdir -p $GH_PAGES/_data/circleci-builds
cp test/test_result.json $GH_PAGES/_data/circleci-builds/${CIRCLE_PIPELINE_NUMBER}_${CIRCLE_BUILD_NUM}.json

pushd $GH_PAGES

git add --all .
git commit -m "CircleCI: test results from job ${CIRCLE_PIPELINE_NUMBER}.${CIRCLE_BUILD_NUM}"

# Allow command to fail (no exit on failure)
set +e

maxAttempts=10
numAttempts=0
success=0
while (( numAttempts != maxAttempts )); do
  numAttempts=$(( numAttempts + 1 ))
  git push -q origin gh-pages
  if [ "$?" != "0" ]; then
    git pull --rebase origin gh-pages
  else
    success=1
    break
  fi
done

popd
