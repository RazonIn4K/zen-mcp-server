# Zen MCP Prompt Playbook

Use these snippets as copy‑and‑paste starters for Zen MCP tool calls. Each template includes the minimum fields you need; swap in the absolute `working_directory`, adjust `model` if you want something other than your default, then drop it into your client. The “Sample Usage” blocks give inspiration for the prompt text you can paste into the template.

---

## Chat – Collaborative Thinking

**Template**
```yaml
Tool: chat
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    {{YOUR_REQUEST}}
```

**Sample Usage**
```text
Summarize the current status of the CTF workspace, list open tasks, and suggest the next two checkpoints to reach by Friday.
```

---

## Analyze – Deep Dive Assessment

**Template**
```yaml
Tool: analyze
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Provide a step-by-step analysis of the selected files.
    Focus: architecture, maintainability, and testing impact.
```

**Sample Usage**
```text
Inspect challenges/leaky_vault/app.py and challenges/caesars_cipher/app/server.py.
- Identify any security weaknesses.
- Flag missing validation or logging.
- Recommend tests needed before release.
```

---

## CodeReview – Pull Request Style Review

**Template**
```yaml
Tool: codereview
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Review the recent changes.
    Mention blocking issues first, then nice-to-have notes.
```

**Sample Usage**
```text
Review the new ctf.py runner and the updates to challenges.json.
Highlight:
- Any violations of the security model.
- Places where error handling is too thin.
- Opportunities to simplify the CLI UX.
```

---

## Debug – Root Cause Investigation

**Template**
```yaml
Tool: debug
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Investigate the reported issue and isolate the root cause.
```

**Sample Usage**
```text
When I run `python ctf.py start caesars-cipher`, docker-compose exits with
`Error response from daemon: driver failed programming external connectivity`.
Trace through the launch sequence and tell me what configuration is missing.
```

---

## TestGen – Generate Tests

**Template**
```yaml
Tool: testgen
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Generate tests for the specified modules.
```

**Sample Usage**
```text
Create pytest tests for:
- challenges/leaky_vault/src/app.py (cover login success/failure and UNION exploit).
- challenges/caesars_cipher/app/server.py (simulate multiple clients hitting the TCP server).
Explain how to run the tests afterward.
```

---

## Refactor – Improvement Plan

**Template**
```yaml
Tool: refactor
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Identify refactoring opportunities and rank them by impact.
```

**Sample Usage**
```text
Scan the ctf.py runner.
- Look for duplicated subprocess code.
- Suggest reorganizing the CLI commands.
- Recommend how to isolate path sanitization into a utility.
```

---

## Planner – Break Down Milestones

**Template**
```yaml
Tool: planner
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Build a multi-step plan with deliverables and checkpoints.
```

**Sample Usage**
```text
Plan the next sprint to deliver three new CTF challenges.
Constraints:
- 5-person team.
- 2-week timeline.
Include milestones for design, implementation, playtesting, and documentation.
```

---

## ThinkDeep – Extended Reasoning

**Template**
```yaml
Tool: thinkdeep
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Perform a high-depth reasoning session on the topic.
```

**Sample Usage**
```text
Evaluate whether we should introduce dynamic flag generation across all challenges.
Consider:
- Security benefits vs. implementation risk.
- Impact on the ctf.py runner.
- How competitors approach this feature.
Provide a recommendation with rationale.
```

---

## Consensus – Multi-Model Evaluation

**Template**
```yaml
Tool: consensus
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Gather multiple stances before the final synthesis.
```

**Sample Usage**
```text
Evaluate the proposal to migrate the CTF infrastructure to Kubernetes.
Use one model pro, one model con, one neutral.
Summarize the key arguments and pick the most balanced recommendation.
```

---

## Clink – Forward to External CLI

**Template**
```yaml
Tool: clink
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    {{instructions for the external CLI agent}}
  cli_name: gemini
  role: default
```

**Sample Usage**
```text
cli_name: gemini
prompt: |
  Run a quick vulnerability scan on the ROT13 server code.
  Flag any obvious denial-of-service vectors.
```

---

## SecAudit – Security Review

**Template**
```yaml
Tool: secaudit
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Perform a security audit focusing on OWASP Top 10.
```

**Sample Usage**
```text
Audit challenges/leaky_vault/src and the related Dockerfile.
List critical/high issues first.
Include suggested mitigations and tests we should add.
```

---

## Precommit – Last-Minute Validation

**Template**
```yaml
Tool: precommit
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Validate the change set before committing.
```

**Sample Usage**
```text
Confirm that the new Caesar’s Cipher challenge is production ready.
Check for:
- Missing documentation.
- Runtime configuration gaps.
- Broken references in challenges.json.
```

---

## API Lookup – Fresh Documentation

**Template**
```yaml
Tool: apilookup
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Research the latest information about {{API_OR_SDK}}.
```

**Sample Usage**
```text
Find the latest Docker Compose release notes for 2025.
Tell me about breaking changes that could affect the CTF runner.
Provide links to primary sources.
```

---

## ListModels / Version – Quick Utilities

**Templates**
```yaml
Tool: listmodels
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Show all available models.
```

```yaml
Tool: version
Arguments:
  model: copilot/gemini-2-5-pro
  working_directory: {{ABS_PATH}}
  prompt: |
    Report the current Zen server version and environment.
```

Use these two commands when you need environment sanity checks or want the MCP client to refresh its model roster.

---

### Tips for Adapting These Snippets

- Replace `{{ABS_PATH}}` with the exact absolute path for the project you’re working on.
- Change the `model` if you prefer a different default (or remove it once `DEFAULT_MODEL` in `.env` is set to a concrete value).
- Mix and match the “Sample Usage” prompts—paste them into any template and tweak details as needed.
- Save your frequently used combinations inside your MCP client so you can apply them with one click.
