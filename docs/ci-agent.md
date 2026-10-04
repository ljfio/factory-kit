# The CI agent (`@claude`)

`.github/workflows/claude.yml` runs [`claude-code-action`](https://github.com/anthropics/claude-code-action) when
the owner comments `@claude` on an issue or pull request. It authenticates with the owner's Claude subscription
(no per-token API bill), so the subscription limits are shared with the owner's own sessions; the workflow caps
turns per run.

## Keeping anyone else from using it

Two independent controls:

1. The job's `if` checks the immutable account id of whoever caused the event; for anyone else the job is
   skipped and no secret is read.
2. The token is an **environment** secret (environment `claude`, deployments limited to the default branch), so
   a run on another branch, or a copy of the workflow edited on a branch, cannot read it.

Do not add `pull_request_review_comment`, `pull_request_review` or `pull_request_target` triggers: they run the
workflow file from the pull request itself.

`.github/CODEOWNERS` asks for the owner's review on workflow, skill and `CLAUDE.md` changes. Enforcing it needs
branch protection or a ruleset, which private repositories on GitHub Free do not have; on public repositories or
a paid plan, enable "Require review from Code Owners" on the default branch.

## Setup

1. Create a long-lived token: `claude setup-token` (uses your subscription).
2. Repository **Settings → Environments → New environment** `claude`. Under *Deployment branches* choose
   *Selected branches* and add the default branch. Add the secret `CLAUDE_CODE_OAUTH_TOKEN` to the environment
   (not the repository secrets).
3. Fill the project setup steps and `--allowedTools` in `claude.yml` for your toolchain.
4. The workflow must be on the default branch before it works (`issue_comment` runs the default branch's copy).
5. Test: comment `@claude summarise this issue` on an issue.

The action is pinned to a commit because that step holds the token; update the pin deliberately.
