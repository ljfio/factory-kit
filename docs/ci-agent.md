# The CI agents (`@claude`, `@codex`)

One workflow per enabled agent, each with the same two controls below. Claude is described first; per-agent secret
and cost sections follow.

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

## Codex (`@codex`)

`.github/workflows/codex.yml` ships only when `codex` is enabled. It runs
[`openai/codex-action`](https://github.com/openai/codex-action) (pinned to the commit of `v1.12`) when the owner
comments `@codex`, with the `:workspace` permission profile (no network), and posts Codex's final message back as a
comment starting `**[Claude]** (Codex)`. It does not push; widen that deliberately if you want it to.

- **Secret and cost:** an OpenAI API key, `OPENAI_API_KEY`, billed per token on your OpenAI account. A ChatGPT
  subscription does not authenticate CI, so unlike `@claude` there is no flat-rate option. Cost is bounded only by
  `timeout-minutes` and the owner-only trigger; set a spend limit on the key.
- **Setup:** as for Claude, but the environment is `codex` (deployments limited to the default branch) and the
  secret is `OPENAI_API_KEY`; run `codex` setup steps for your toolchain before the Codex step.
- **Controls:** the same `if` (sender id, repository owner, `@codex`, not a `**[Claude]**` reply) and
  environment-scoped secret. The action itself also refuses callers without write access.
