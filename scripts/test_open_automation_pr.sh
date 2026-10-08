#!/usr/bin/env bash
# shellcheck disable=SC2016 # backticks in single quotes are Markdown code spans
set -Eeuo pipefail

source_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
script="$source_root/scripts/open_automation_pr.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin"

# gh stand-in: logs "<token> gh <args>" and answers from files in $MOCK_GH_DIR,
# already shaped the way the script's --jq filters would print them.
cat >"$tmp/bin/gh" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
dir=${MOCK_GH_DIR:?}
printf '%s gh %s\n' "${GH_TOKEN:-}" "$*" >>"$dir/log"
body_file='' previous=''
for arg in "$@"; do
  if [[ $previous == --body-file ]]; then body_file=$arg; fi
  previous=$arg
done
case "$1 $2" in
  "pr list")
    if [[ " $* " == *" --head "* ]]; then
      cat "$dir/pr_for_head" 2>/dev/null || true
    else
      cat "$dir/open_prs" 2>/dev/null || true
    fi
    ;;
  "pr create")
    if [[ -f $dir/refuse_pr ]]; then
      echo "pull request create failed: GraphQL: GitHub Actions is not permitted to create or approve pull requests (createPullRequest)" >&2
      exit 1
    fi
    echo "https://github.com/o/r/pull/7"
    ;;
  "issue list") cat "$dir/open_issues" 2>/dev/null || true ;;
  "issue create")
    if [[ -f $dir/refuse_issue ]]; then
      echo "HTTP 410: Issues are disabled for this repo" >&2
      exit 1
    fi
    echo "https://github.com/o/r/issues/12"
    ;;
  "issue edit") cp "$body_file" "$dir/issue.md" ;;
  "issue comment")
    cp "$body_file" "$dir/issue.md"
    echo "https://github.com/o/r/issues/$3#issuecomment-1"
    ;;
  "pr close" | "issue close" | "api -X") ;;
  *)
    echo "unexpected gh call: $*" >&2
    exit 64
    ;;
esac
EOF
chmod +x "$tmp/bin/gh"

export PATH="$tmp/bin:$PATH"
export GITHUB_REPOSITORY=o/r GITHUB_SERVER_URL=https://github.com GITHUB_RUN_ID=99
export GH_TOKEN=app ISSUE_GH_TOKEN=workflow

printf 'New sha256: `abc`.\nLine & more #1 → done\n' >"$tmp/body.md"
head -c 7000 /dev/zero | tr '\0' 'x' >"$tmp/long.md"

fail() {
  printf 'FAIL [%s]: %s\n' "$case_name" "$*" >&2
  for file in log out err issue.md; do
    if [[ -f $MOCK_GH_DIR/$file ]]; then printf -- '--- %s\n' "$file" >&2; cat "$MOCK_GH_DIR/$file" >&2; fi
  done
  exit 1
}
start() {
  case_name=$1
  export MOCK_GH_DIR="$tmp/$1"
  export GITHUB_STEP_SUMMARY="$MOCK_GH_DIR/summary"
  mkdir -p "$MOCK_GH_DIR"
  : >"$MOCK_GH_DIR/log"
}
open_pr() {
  bash "$script" --base main --head kb-refresh/sha-new --title 'Refresh KB (sha256)' \
    --body-file "${body:-$tmp/body.md}" --supersede kb-refresh/sha- \
    >"$MOCK_GH_DIR/out" 2>"$MOCK_GH_DIR/err"
}
has() { grep -qF -- "$2" "$MOCK_GH_DIR/$1" || fail "$1 lacks: $2"; }
lacks() { ! grep -qF -- "$2" "$MOCK_GH_DIR/$1" || fail "$1 has: $2"; }
prints() { [[ $(cat "$MOCK_GH_DIR/out") == "$1" ]] || fail "printed '$(cat "$MOCK_GH_DIR/out")', want '$1'"; }

start opens_the_pr
open_pr || fail "exit $?"
prints https://github.com/o/r/pull/7
has log 'app gh pr create --base main --head kb-refresh/sha-new --title Refresh KB (sha256) --body-file'
has summary 'Opened https://github.com/o/r/pull/7'
lacks log 'issue create'

start reports_an_open_pr
echo https://github.com/o/r/pull/5 >"$MOCK_GH_DIR/pr_for_head"
open_pr || fail "exit $?"
prints https://github.com/o/r/pull/5
has summary 'Already open: https://github.com/o/r/pull/5'
lacks log 'pr create'

start falls_back_to_an_issue
touch "$MOCK_GH_DIR/refuse_pr"
open_pr || fail "a refused PR must not fail the run (exit $?)"
prints ''
has log 'workflow gh issue create --title Open the pull request for kb-refresh/sha-new'
has log 'workflow gh issue edit 12 --body-file'
has err '::warning title=Pull request not opened::GitHub refused to open the pull request for kb-refresh/sha-new (pull request create failed: GraphQL: GitHub Actions is not permitted to create or approve pull requests (createPullRequest)). Open it from https://github.com/o/r/issues/12.'
# Every byte but unreserved characters is encoded, UTF-8 (→) byte by byte.
has issue.md '(https://github.com/o/r/compare/main...kb-refresh/sha-new?quick_pull=1&title=Refresh%20KB%20%28sha256%29&body=New%20sha256%3A%20%60abc%60.%0ALine%20%26%20more%20%231%20%E2%86%92%20done%0A%0ACloses%20%2312)'
has issue.md 'with its title and description filled in.'
has issue.md '> pull request create failed: GraphQL: GitHub Actions is not permitted'
has issue.md 'Reported by https://github.com/o/r/actions/runs/99.'
has summary '### Pull request not opened'
has summary 'tracked in https://github.com/o/r/issues/12.'

start updates_its_issue_on_a_rerun
touch "$MOCK_GH_DIR/refuse_pr"
printf '30\tOpen the pull request for kb-refresh/sha-new\n' >"$MOCK_GH_DIR/open_issues"
open_pr || fail "exit $?"
has log 'workflow gh issue comment 30 --body-file'
lacks log 'issue create'
has issue.md 'Closes%20%2330'
has err 'Open it from https://github.com/o/r/issues/30#issuecomment-1.'

start supersedes_older_branches
printf '3\tkb-refresh/sha-old\n4\tengine-bump/abc\n7\tkb-refresh/sha-new\n' >"$MOCK_GH_DIR/open_prs"
printf '21\tOpen the pull request for kb-refresh/sha-older\n22\tOpen the pull request for engine-bump/xyz\n23\tUnrelated kb-refresh/sha- issue\n' >"$MOCK_GH_DIR/open_issues"
open_pr || fail "exit $?"
has log 'app gh pr close 3 --delete-branch --comment Superseded by https://github.com/o/r/pull/7.'
lacks log 'pr close 4'
lacks log 'pr close 7'
has log 'workflow gh issue close 21 --comment Superseded by https://github.com/o/r/pull/7.'
has log 'app gh api -X DELETE repos/o/r/git/refs/heads/kb-refresh/sha-older'
lacks log 'issue close 22'
lacks log 'issue close 23'

start supersedes_after_falling_back
touch "$MOCK_GH_DIR/refuse_pr"
printf '3\tkb-refresh/sha-old\n' >"$MOCK_GH_DIR/open_prs"
open_pr || fail "exit $?"
has log 'app gh pr close 3 --delete-branch --comment Superseded by https://github.com/o/r/issues/12.'

start long_descriptions_are_pasted
touch "$MOCK_GH_DIR/refuse_pr"
body="$tmp/long.md" open_pr || fail "exit $?"
has issue.md '?quick_pull=1&title=Refresh%20KB%20%28sha256%29)'
lacks issue.md '&body='
has issue.md 'with its title filled in.'
has issue.md "$(head -c 7000 "$tmp/long.md")"
has issue.md 'Closes #12'

start fails_without_a_pr_or_an_issue
touch "$MOCK_GH_DIR/refuse_pr" "$MOCK_GH_DIR/refuse_issue"
if open_pr; then fail "must fail when neither a PR nor an issue opens"; fi
has err 'Issues are disabled'

start rejects_bad_usage
if bash "$script" --base main --head x >/dev/null 2>"$MOCK_GH_DIR/err"; then fail "accepted missing arguments"; fi
has err 'usage:'

printf 'automation PR tests passed\n'
