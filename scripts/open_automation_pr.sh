#!/usr/bin/env bash
# Open the pull request for an automation branch that is already pushed.
#
# GitHub refuses when the organization doesn't let Actions create pull
# requests. Rather than end a run red after its real work succeeded, this opens
# (or updates) an issue with a link that opens the pull request in one click,
# title and description filled in. A pull request a person opens also runs the
# required checks, which one opened with the workflow token doesn't.
#
# Usage: open_automation_pr.sh --base BRANCH --head BRANCH --title TEXT
#                              --body-file FILE [--supersede PREFIX]
#
# --supersede closes the other open pull requests and fallback issues whose
# branch starts with PREFIX, such as an older KB checksum or engine bump.
#
# Prints the pull request URL, or nothing when it fell back to an issue.
# GH_TOKEN opens the pull request; ISSUE_GH_TOKEN (default: GH_TOKEN) manages
# issues, which the automation App has no permission for.
# shellcheck disable=SC2016 # backticks in single quotes are Markdown code spans
set -Eeuo pipefail

usage() {
  echo "usage: $0 --base BRANCH --head BRANCH --title TEXT --body-file FILE [--supersede PREFIX]" >&2
  exit 2
}

base='' head='' title='' body_file='' supersede=''
while (($#)); do
  (($# >= 2)) || usage
  case $1 in
    --base) base=$2 ;;
    --head) head=$2 ;;
    --title) title=$2 ;;
    --body-file) body_file=$2 ;;
    --supersede) supersede=$2 ;;
    *) usage ;;
  esac
  shift 2
done
[[ -n $base && -n $head && -n $title && -f $body_file ]] || usage

repo=${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is not set}
server=${GITHUB_SERVER_URL:-https://github.com}
run_url="$server/$repo/actions/runs/${GITHUB_RUN_ID:-}"
summary=${GITHUB_STEP_SUMMARY:-/dev/null}
issue_prefix='Open the pull request for '
issue_title="$issue_prefix$head"
max_link=6000 # GitHub answers longer compare URLs with 414 URI Too Long
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

issue_gh() { GH_TOKEN=${ISSUE_GH_TOKEN:-${GH_TOKEN:-}} gh "$@" </dev/null; }

# Percent-encode every byte except RFC 3986 unreserved characters.
urlencode() {
  local hex byte char out='' i
  hex=$(printf '%s' "$1" | od -An -tx1 -v | tr -d ' \n')
  for ((i = 0; i < ${#hex}; i += 2)); do
    byte=${hex:i:2}
    case $byte in
      3[0-9] | 4[1-9a-f] | 5[0-9a] | 6[1-9a-f] | 7[0-9a] | 2d | 2e | 5f | 7e)
        printf -v char '%b' "\\x$byte"
        out+=$char
        ;;
      *) out+="%${byte^^}" ;;
    esac
  done
  printf '%s' "$out"
}

# Open fallback issues as "number<TAB>branch" for branches starting with $1.
fallback_issues() {
  issue_gh issue list --state open --limit 100 --search "in:title \"$issue_prefix\"" \
    --json number,title --jq '.[] | "\(.number)\t\(.title)"' |
    while IFS=$'\t' read -r number found; do
      if [[ $found == "$issue_prefix$1"* ]]; then
        printf '%s\t%s\n' "$number" "${found#"$issue_prefix"}"
      fi
    done
}

# Close the other pull requests and fallback issues of --supersede branches.
supersede_others() {
  [[ -n $supersede ]] || return 0
  local number branch
  gh pr list --state open --limit 100 --json number,headRefName \
    --jq '.[] | "\(.number)\t\(.headRefName)"' |
    while IFS=$'\t' read -r number branch; do
      if [[ $branch == "$supersede"* && $branch != "$head" ]]; then
        gh pr close "$number" --delete-branch --comment "Superseded by $1." </dev/null >&2 || true
      fi
    done
  fallback_issues "$supersede" |
    while IFS=$'\t' read -r number branch; do
      if [[ $branch != "$head" ]]; then
        issue_gh issue close "$number" --comment "Superseded by $1." >&2 || true
        gh api -X DELETE "repos/$repo/git/refs/heads/$branch" </dev/null >/dev/null 2>&1 || true
      fi
    done
}

pr_url=$(gh pr list --state open --head "$head" --json url --jq '.[0].url // empty' </dev/null)
if [[ -n $pr_url ]]; then
  echo "Already open: $pr_url" | tee -a "$summary" >&2
elif pr_url=$(gh pr create --base "$base" --head "$head" --title "$title" \
  --body-file "$body_file" </dev/null 2>"$tmp/error"); then
  echo "Opened $pr_url" | tee -a "$summary" >&2
else
  pr_url=''
fi
if [[ -n $pr_url ]]; then
  supersede_others "$pr_url"
  printf '%s\n' "$pr_url"
  exit 0
fi

cat "$tmp/error" >&2
reason=$(grep -v '^[[:space:]]*$' "$tmp/error" | tail -n 1 || true)
reason=${reason:-gh pr create failed}

number='' issue_url=''
while IFS=$'\t' read -r found branch; do
  if [[ $branch == "$head" ]]; then number=$found; fi
done < <(fallback_issues "$head")
if [[ -z $number ]]; then
  issue_url=$(issue_gh issue create --title "$issue_title" \
    --body "Preparing the link that opens the pull request for \`$head\`.")
  number=${issue_url##*/}
fi

pr_body="$(cat "$body_file")"$'\n\n'"Closes #$number"
link="$server/$repo/compare/$base...$head?quick_pull=1&title=$(urlencode "$title")"
encoded_body="&body=$(urlencode "$pr_body")"
if ((${#link} + ${#encoded_body} <= max_link)); then
  link+=$encoded_body
  filled='title and description'
else
  filled='title'
fi
{
  printf "GitHub Actions couldn't open the pull request for \`%s\`:\n\n> %s\n\n" "$head" "$reason"
  printf 'The branch is pushed. **[Open the pull request](%s)** with its %s filled in.' "$link" "$filled"
  printf ' Because a person opens it, the required checks run. Merging it closes this issue.\n'
  if [[ $filled == title ]]; then
    printf '\nThe description is too long for the link, so paste it:\n\n````markdown\n%s\n````\n' "$pr_body"
  fi
  printf '\nReported by %s.\n' "$run_url"
} >"$tmp/issue.md"

if [[ -n $issue_url ]]; then
  issue_gh issue edit "$number" --body-file "$tmp/issue.md" >/dev/null
else
  issue_url=$(issue_gh issue comment "$number" --body-file "$tmp/issue.md")
fi

message="GitHub refused to open the pull request for $head ($reason). Open it from $issue_url."
message=${message//'%'/'%25'}
echo "::warning title=Pull request not opened::${message//$'\n'/'%0A'}" >&2
{
  printf '### Pull request not opened\n\n%s\n\n' "$reason"
  printf '[Open the pull request](%s) for `%s`; tracked in %s.\n' "$link" "$head" "$issue_url"
} >>"$summary"
supersede_others "$issue_url"
