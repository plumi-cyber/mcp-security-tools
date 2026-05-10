# MCP Security Tools — Build Log

A working notebook for building a Model Context Protocol server that exposes
security-relevant tools to an AI agent. This document is updated as the project
progresses — challenges, solutions, decisions, and the reasoning behind them.

**Author:** Lumi (plumi-cyber)
**Started:** May 9, 2026
**Target completion:** May 10, 2026 (two evenings)
**Repo:** `mcp-security-tools` (to be pushed to GitHub on evening two)

---

## Why this project exists

PointClickCare is hiring for a security analyst role on an "agentic AI-augmented
SOC platform." That phrase translates to: AI agents that call security tools
(SIEM queries, threat intel lookups, endpoint actions) through a protocol layer.

The hiring signal in that posting is that they want someone who understands how
AI assistants and security tools talk to each other — not someone who has just
read about it. A working public artifact that demonstrates this pattern closes
the credibility gap on the application.

The same artifact is reusable across any AI-forward security role going forward.

## Scope

Two tools, exposed via one MCP server, callable by Claude Desktop:

1. **Auth log parser** — reads a sample SSH auth log file, returns failed login
   attempts grouped by source IP.
2. **IP reputation check** — queries AbuseIPDB's free API to check if an IP has
   been reported as malicious.

The agent demo: feed it a fake auth log, ask it to find suspicious IPs and
check whether they're known bad actors. End-to-end agentic security workflow,
under 200 lines of code, no live infrastructure.

## Architecture from first principles

### What MCP is

**Model Context Protocol.** A standard format for how AI assistants call
external tools. Anthropic published it openly so any model and any tool can
talk to each other without bespoke glue code each time.

Mental model: imagine Claude as a brilliant analyst working in a sealed room.
On their own, they can think and write but can't reach out and check anything
in the real world — no database queries, no file reads, no API calls. To fix
that, you slide tools through a slot in the wall. Each tool is a function:
"look up this IP," "read that log file," "send this email." The analyst sees
a list of available tools, picks one, slides a request through, and gets a
result back.

MCP is the agreed-upon shape of that slot.

### MCP server vs. client

- An **MCP server** is the thing on the tool side of the slot. A program that
  says "here are the tools I expose, here are their inputs and outputs, and
  here's the code that runs when you call them."
- An **MCP client** is the thing on the AI side. Claude Desktop is an MCP
  client — when it starts, it reads its config, launches each registered MCP
  server as a subprocess, asks "what tools do you have?", and makes those
  tools available to the AI inside the chat.

These are entirely decoupled. My server doesn't know or care that it's Claude
on the other end — it would work identically with any MCP client. Claude
Desktop doesn't know or care what my server does internally — it just sees a
list of tools with descriptions and schemas.

That decoupling is why this pattern matters in security. PointClickCare's
"agentic SOC platform" works this way: one AI brain, dozens of tools (SIEM,
EDR, ticketing, threat intel) all behind the same protocol. The brain doesn't
need a custom integration for each.

### What an SDK is, and why we use one

**Software Development Kit.** A bundle of pre-built code someone hands you so
you don't have to build the basics from scratch.

Pharmacy analogy: when compounding a prescription, you didn't synthesize the
active ingredient from raw chemicals. You opened a jar of pre-manufactured
API powder, weighed it out, and combined it with a base. The hard chemistry
was already done. SDKs work the same way — the hard infrastructure is
pre-built; you focus on the application-specific work.

The MCP protocol itself involves message schemas, lifecycle events, transport
handshakes. Implementing it directly would be tedious. The official MCP Python
SDK (the `mcp` package on PyPI) exposes a high-level helper class called
**FastMCP** that hides all of it. I write normal Python functions and slap
`@mcp.tool()` on top. The helper inspects each function — reads the type hints,
reads the docstring — and generates the protocol-level schema automatically.

Result: an 8-line `server.py` that does what would otherwise be hundreds of
lines of protocol code.

---

## Evening 1 — Build Log

**Goal:** environment fully set up; a "hello world" MCP server that Claude
Desktop can see and call. Nothing more.

**Time spent:** ~3 hours (most of it on a Microsoft-Store sandbox issue that
had nothing to do with the code itself).

### Phase 1 — Install the four tools

| Tool | Version | Why |
|---|---|---|
| Python | 3.14 (x64) | Runtime for the MCP server. 3.14 has wheels available for all dependencies. |
| Git for Windows | latest x64 | Version control. The CPU architecture is determined by `$env:PROCESSOR_ARCHITECTURE`. |
| VS Code | latest | Editor with Python extension. |
| Claude Desktop | 1.6608.2 | The MCP client that will load and call my server. |

**Git installer choices that mattered:**

- **PATH option:** middle option ("Git from the command line and also from 3rd-party software"). The first option only enables Git in Git Bash; the third pollutes PATH with the entire Unix toolset.
- **SSH:** bundled OpenSSH (self-contained, no PATH conflicts).
- **HTTPS backend:** OpenSSL (portable across machines and environments; matches every tutorial online).
- **Line endings:** "Checkout as-is, commit Unix-style line endings." Linux/macOS/GitHub all use LF; auto-conversion creates phantom diffs and breaks shell scripts.
- **Credential helper:** Git Credential Manager. Handles GitHub OAuth automatically — no manual personal access token management.
- **Default branch:** `main` (modern convention; what every tutorial assumes).

**Challenge encountered:** after the Git install, `git --version` in PowerShell returned "not recognized." Cause: PowerShell loads PATH on startup; new programs don't appear in already-running shells. **Fix:** close and reopen PowerShell. Same issue later with the `code` command for VS Code, same fix.

### Phase 2 — Project skeleton + hello-world server

**Project structure:**
```
C:\Users\pelum\projects\mcp-security-tools\
├── .venv\                    # virtual environment (Python + packages)
├── server.py                 # the MCP server itself
└── (more files coming evening 2)
```

**Virtual environment.** Created with `python -m venv .venv` and activated with
`.\.venv\Scripts\Activate.ps1`. Mental model: a sealed lunchbox. Packages
installed into the .venv stay in the .venv, not on the system Python. When
`(.venv)` shows in the PowerShell prompt, I'm working inside it.

**Challenge encountered:** activating the venv failed with "running scripts is
disabled on this system" — PowerShell's default execution policy blocks local
scripts. **Fix (one-time):**
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
Scoped to my user only, which is the standard developer setting on Windows.

**Packages installed:**
```powershell
pip install "mcp[cli]" requests python-dotenv
```
- `mcp[cli]` — the official Anthropic SDK plus its CLI tools.
- `requests` — for the AbuseIPDB HTTP call (evening 2).
- `python-dotenv` — loads the AbuseIPDB API key from a `.env` file instead of hardcoding it.

**The hello-world server (`server.py`):**

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("security-tools")

@mcp.tool()
def hello(name: str) -> str:
    """Says hello to confirm the MCP server is wired up."""
    return f"Hello from your MCP security-tools server, {name}!"

if __name__ == "__main__":
    mcp.run()
```

What each line does:
- Line 1: imports the high-level helper class from the SDK.
- Line 3: creates a server instance named `"security-tools"`. This name appears in the Claude Desktop UI.
- Line 5: the `@mcp.tool()` decorator turns a regular Python function into a tool an AI agent can call. The docstring becomes the tool's description that the agent reads to decide when to use it. The type hints (`name: str`, `-> str`) become the input/output schema automatically.
- Line 11: starts the protocol loop that listens for incoming tool calls.

**Challenge encountered:** when I created `server.py` through VS Code, the file ended up somewhere other than the project folder. `python server.py` returned "No such file or directory." **Fix:** wrote the file directly from PowerShell using a here-string (`@'...'@ | Out-File`), which guarantees it lands in the current working directory.

**Sanity-checked the server:** `python server.py` produced no output and didn't return to the prompt. That's the correct behavior — the server is listening on stdin/stdout for an MCP client to connect. `Ctrl+C` stops it. The interrupt printed a long traceback (`anyio.WouldBlock`, `KeyboardInterrupt`) which **looked** like an error but was actually Python's verbose shutdown logging when interrupted mid-wait.

### Phase 3 — Wire the server into Claude Desktop

This phase took ~80% of the evening. Single root cause buried under three layers of false leads.

**The intended workflow:**
1. Edit `claude_desktop_config.json` to register the server.
2. Restart Claude Desktop fully.
3. The tool appears in the Claude Desktop UI.

**The intended config file:**

```json
{
  "mcpServers": {
    "security-tools": {
      "command": "C:\\Users\\pelum\\projects\\mcp-security-tools\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\pelum\\projects\\mcp-security-tools\\server.py"
      ]
    }
  }
}
```

Key technical points:
- **Double backslashes** in JSON. JSON treats `\` as an escape character (e.g., `\n` for newline). Windows paths require each backslash to be doubled in JSON. Single most common JSON config bug.
- **The `command` field points at the venv's python.exe**, not the system Python. The venv is the only Python installation that has the `mcp` package — system Python would crash on the import.

#### Challenge 1: the config folder didn't exist

`notepad $env:APPDATA\Claude\claude_desktop_config.json` returned "system cannot find the path specified." Notepad will create a missing file but not the missing folders above it.

**Fix:**
```powershell
New-Item -ItemType Directory -Path $env:APPDATA\Claude -Force
notepad $env:APPDATA\Claude\claude_desktop_config.json
```

#### Challenge 2: the file was saved, but Claude Desktop showed nothing

After saving the config and restarting Claude Desktop, no tool icon appeared in the chat UI. No `logs/` folder was created either, suggesting Claude Desktop never even attempted to launch the server.

I checked three things in order:

1. **Was the config file actually saved?** `cat $env:APPDATA\Claude\claude_desktop_config.json` printed the JSON correctly. ✓
2. **Were stale Claude processes preventing config reload?** `Get-Process -Name Claude | Stop-Process -Force` cleared everything. Restarted. Still nothing.
3. **Did the executable paths in the config exist?** `Test-Path` on both python.exe and server.py returned `True`. ✓

The config existed. The paths were valid. Claude Desktop was restarted cleanly. Yet no logs folder was created and no tool appeared.

#### Challenge 3 (the real cause): Microsoft Store app sandbox

In Claude Desktop, navigated to **Settings → Developer → Local MCP servers**.
The panel showed "No servers added" with an "Edit Config" button.

![No servers added — but our config file existed elsewhere](screenshots/03_no_servers_added.png)

When I clicked **Edit Config**, the config file that opened was at this path:

![The Microsoft Store sandbox redirected our config to a private folder](screenshots/04_store_sandbox_path.png)

```
C:\Users\pelum\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json
```

That weird path is the giveaway. Claude Desktop was installed from the **Microsoft Store**, not from claude.ai/download. Store apps run inside a sandbox — when they try to read or write to `AppData\Roaming`, Windows silently redirects them to a per-app private folder under `AppData\Local\Packages\<package_name>\LocalCache\Roaming\`.

**Plain analogy:** a Store app is like an employee who's only allowed to use one specific filing cabinet that has their name on it. Even if they ask for "the Roaming filing cabinet," Windows secretly hands them their personal one. The config I wrote earlier at the regular `Roaming\Claude\` location was sitting in a cabinet Claude Desktop literally couldn't see.

The file Claude Desktop **actually** reads was already populated by the app with `"preferences"`, `"coworkScheduledTasksEnabled"`, etc. — but no `mcpServers` block.

**Fix:** add the `mcpServers` block alongside the existing `preferences` block in the sandboxed config file (not a new file at the regular `Roaming` location). JSON requires commas between sibling fields:

```json
{
  "preferences": {
    "coworkScheduledTasksEnabled": true,
    "ccdScheduledTasksEnabled": true,
    "sidebarMode": "chat",
    "coworkWebSearchEnabled": true,
    "epitaxyPrefs": { ... }
  },
  "mcpServers": {
    "security-tools": {
      "command": "C:\\Users\\pelum\\projects\\mcp-security-tools\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\pelum\\projects\\mcp-security-tools\\server.py"
      ]
    }
  }
}
```

**Then a clean restart via Task Manager** (Microsoft Store apps don't always quit cleanly via the system tray):

1. `Ctrl+Shift+Esc` → Task Manager
2. End every "Claude" process
3. Launch Claude Desktop fresh from Start menu

### Phase 4 — Milestone

After the sandbox-aware fix, Settings → Developer → Local MCP servers shows:

![The milestone — security-tools running, server is live](screenshots/05_security_tools_running.png)

- `security-tools` listed ✓
- Status badge: **running** (in blue) ✓
- Command: points at the venv python.exe ✓
- Arguments: points at server.py ✓

This means Claude Desktop launched my server as a subprocess, the protocol handshake completed, and the connection is live. Evening 1 milestone hit.

---

## Conceptual learnings consolidated

### 1. Virtual environments aren't optional

A Python virtual environment is a sealed, project-specific copy of the Python interpreter and the packages installed for that project. Not using one is how you end up with global package conflicts that destroy unrelated projects when one of them updates a dependency. Activating the venv (`.venv\Scripts\Activate.ps1` on Windows) repoints the shell's `python` and `pip` commands at the venv's copies. The `(.venv)` prefix in the prompt is the visual cue.

### 2. PATH is loaded once per shell

When a Windows installer adds a new program to PATH, **already-running** terminals don't see the change. The PATH a process inherits is fixed at the moment that process started. This is why `git --version` and `code` both came up "not recognized" right after install — closing and reopening PowerShell fixed both. The principle generalizes: any "command not recognized" error immediately after installing something is probably a stale-PATH issue first, real install problem second.

### 3. JSON syntax is unforgiving

JSON has three rules that bite Windows users specifically:
- Backslashes in strings must be escaped: `"C:\\Users\\..."`, not `"C:\Users\..."`.
- Sibling fields inside an object are comma-separated. Missing comma = parse error = silent config rejection.
- No trailing commas allowed (unlike Python). `[1, 2, 3,]` is valid Python, invalid JSON.

A single missing comma or single backslash makes Claude Desktop silently ignore the entire file. Worth getting comfortable with running configs through `cat` and re-reading carefully.

### 4. Microsoft Store apps run in a sandbox

This is the biggest gotcha I hit and the most generally useful one to remember. Apps installed from the Microsoft Store are containerized — their reads and writes to `AppData\Roaming` are silently redirected to a private per-app folder under `AppData\Local\Packages\<package_name>\LocalCache\Roaming\`. Tutorials that say "edit your config at `%APPDATA%\AppName\config.json`" assume the non-Store install. If you installed from the Store, you must edit through the app's UI (which knows the sandboxed path) rather than the documented path, or reinstall from the direct download.

### 5. MCP is decoupled by design

The server doesn't know which client is talking to it. The client doesn't know what tools the server actually does internally — only their schemas and descriptions. This is why one MCP server can be reused across Claude Desktop, custom agents, IDE extensions, and any future MCP-aware tool without modification. It's also why this pattern scales for a real SOC: one AI brain calling dozens of independently-developed tools through one protocol.

---

## Troubleshooting reference

| Symptom | Cause | Fix |
|---|---|---|
| `git --version` → "not recognized" | PowerShell PATH stale | Close and reopen PowerShell |
| `code .` → "not recognized" | Same — VS Code's PATH entry not loaded | Close and reopen PowerShell, or open VS Code manually |
| `Activate.ps1 cannot be loaded` | PowerShell execution policy | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `python server.py` → "No such file" | File saved outside project folder | Use here-string in PowerShell to write it directly: `@'...'@ \| Out-File -FilePath server.py` |
| Long Python traceback on `Ctrl+C` | Not an error — verbose shutdown logging | Look for `KeyboardInterrupt` at the bottom; the server was working |
| `notepad $env:APPDATA\Claude\config.json` → "system cannot find the path specified" | Folder doesn't exist yet | `New-Item -ItemType Directory -Path $env:APPDATA\Claude -Force` |
| MCP server shows "No servers added" despite saving config | Microsoft Store sandbox redirects config writes | Edit the config via Settings → Developer → Edit Config (which opens the sandboxed path) instead of the documented path |
| Claude Desktop won't pick up config changes | Stale process in system tray | Use Task Manager (`Ctrl+Shift+Esc`) → End all Claude processes → relaunch from Start menu |

---

## Evening 2 plan (next session)

**Replace the `hello` tool with two real ones:**

1. `parse_auth_log(filepath: str) -> list[dict]` — opens a sample auth log committed to the repo, scans for `Failed password` events, returns each event with timestamp, source IP, and target username. Counts attempts per source IP.
2. `check_ip_reputation(ip: str) -> dict` — calls the AbuseIPDB API (key loaded from `.env`), returns the abuse confidence score, last reported time, country, and ISP.

**Sample data:** a hand-crafted auth log (`sample_data/auth.log`) with several normal entries plus a few suspicious patterns (rapid-fire failures from one IP, distributed brute force from many IPs, success after many failures).

**The agent demo flow:**
- Open Claude Desktop, point it at the auth log
- Ask: "Investigate this auth log. Are any of the source IPs known malicious?"
- The agent calls `parse_auth_log` → identifies suspicious IPs → calls `check_ip_reputation` for each → summarizes findings

**README.md** — the part hiring managers actually read. Will frame the project around healthcare-security relevance for PointClickCare without overstating fit. Will include the GIF/video of the demo running.

**30-second screen capture** — the demo embedded in the README. Worth more than another 500 lines of code.

**Push to GitHub** at `plumi-cyber/mcp-security-tools` — public, MIT-licensed.

---

## Architecture diagram

```
┌──────────────────────┐         MCP protocol          ┌─────────────────────────┐
│   Claude Desktop     │ ◄────── (stdio JSON) ──────► │  server.py (my code)    │
│   (MCP client)       │                              │  FastMCP from SDK       │
│                      │                              │                         │
│  - launches server   │  "what tools do you have?"   │  @mcp.tool()            │
│    as subprocess     │                              │  parse_auth_log()       │
│  - reads tool list   │  "call parse_auth_log with…" │                         │
│  - lets the AI       │                              │  @mcp.tool()            │
│    decide when to    │  "result: [...]"             │  check_ip_reputation()  │
│    call them         │                              │     │                   │
└──────────────────────┘                              └─────│───────────────────┘
                                                            │
                                                            ▼
                                                   ┌────────────────────┐
                                                   │  AbuseIPDB API     │
                                                   │  (HTTPS + API key) │
                                                   └────────────────────┘
```

The agent (Claude) sits on the left. My code sits on the right. The MCP
protocol is the slot in the wall between them. AbuseIPDB is one of the things
my tools reach out to in the real world.

This is the same shape PointClickCare's agentic SOC platform uses — substitute
"Claude" with their agent runtime, substitute my two tools with their dozens
of security integrations.
---

## Evening 2 — Build Log

**Goal:** replace the placeholder `hello` tool with two real ones, get the
end-to-end agent investigation working, ship the README and push the public
GitHub repo.

**Time spent:** ~5 hours (longer than evening 1 because the agent demo had a
non-obvious failure mode that required reasoning about filesystem boundaries
between the agent and the MCP server).

### Phase 1 — Build the auth log parser tool

#### Sample data design

The sample auth log isn't arbitrary — it's hand-crafted with five distinct
attack patterns chosen to demonstrate tiered SOC reasoning:

| Pattern | Source IP | Shape | Why it's here |
|---|---|---|---|
| Successful credential compromise | 103.211.18.97 | 5 rapid failures, then 1 success on a real user (`lumi`) | Highest priority: the line between attempted and confirmed breach |
| Aggressive brute force | 185.220.101.42 | 8 failures in 21 seconds, cycling 5 admin-style usernames | High volume but typically blocked by rate limits; Tor exit node |
| Username spray | 45.155.205.233 | 3 failures testing `test`, `user`, `guest` | Opportunistic probing, lower priority |
| Quiet probe | 91.240.118.222 | 2 admin-targeted failures spaced ~7 seconds apart | Reconnaissance |
| Normal traffic | 192.168.1.45, .1.62 | Successful logins from internal IPs | Noise — should be filtered out |

The point: with this data, an agent that just sorts by attempt count produces
the wrong triage. The credential compromise has only 5 attempts but is the
most serious finding. A good agent has to reason about *patterns*, not just
*counts*. By engineering the data this way, the demo proves the agent is
doing more than running aggregations.

#### The parser implementation

Core approach: regex pattern-match `Failed password` lines, group by source
IP, return sorted by attempt count descending.

```python
FAILED_LOGIN_PATTERN = re.compile(
    r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>\d+\.\d+\.\d+\.\d+)"
)
```

Reading the regex left to right:
- `Failed password for` — literal
- `(?:invalid user )?` — optionally consume "invalid user " without capturing it
- `(?P<user>\S+)` — capture the username into a named group
- ` from ` — literal
- `(?P<ip>\d+\.\d+\.\d+\.\d+)` — capture an IPv4 address

Named groups (`(?P<name>...)`) are easier to read at the call site than
positional capture groups. Worth the slight extra syntax.

#### Why a regex and not string splitting

Auth log lines vary — some have "invalid user," some don't, extra fields can
appear. A regex pins down the exact shape and ignores everything else. It's
also the same skill used in production SIEM tools — Splunk's `rex` command,
Sentinel's KQL `parse` operator, Elastic's grok patterns are all regex
variants. Different syntax, same mental model.

#### Conceptual choices in the function shape

- **`defaultdict` instead of manual dict initialization** — saves an
  if-key-exists check on every line.
- **Sets for usernames, converted to sorted lists at output** — sets
  auto-deduplicate; lists are JSON-serializable for MCP transport.
- **First/last seen timestamps** — frame the attack window; lets the agent
  reason about timing density (8 attempts in 21 seconds vs 8 attempts over
  a day means very different things).
- **Sort by attempt count descending** — noisiest sources surface first in
  the agent's view.

#### Standalone testing

Tested in a Python REPL (`from server import parse_auth_log`) before touching
MCP. Output:

- Total failed attempts: 18 ✓
- Unique source IPs: 4 (the four attacking IPs; internal IPs from successful
  logins are correctly excluded)
- 185.220.101.42 leading with 8 attempts cycling 5 usernames ✓
- 103.211.18.97 with 5 attempts targeting only `lumi` ✓

**Debugging principle reinforced:** test each piece in isolation before wiring
pieces together. If the demo fails later, you immediately know whether the
problem is in the tool or in the integration. Skipping standalone testing
turns one easy bug into two compound bugs.

### Phase 2 — Build the AbuseIPDB tool

#### Secrets management

Created two files together: `.env` (the secret) and `.gitignore` (Git's
blocklist that includes `.env`).

The pattern: secrets in `.env`, code reads them via `python-dotenv`, `.env`
is in `.gitignore` so it never gets committed. Anyone cloning the repo gets
the *code* that reads the secret, never the secret itself.

Why this matters concretely: bots scan public GitHub commits continuously for
exposed API keys. Average exposure-to-abuse window for an AWS key is under 60
seconds. AbuseIPDB keys are less catastrophic, but the habit of using
`.env` + `.gitignore` from day one means the same instinct kicks in on a more
sensitive project later.

The `.env.example` template gets committed (with a placeholder value) so
people cloning the repo know what variables they need to set without seeing
the real key.

#### The API wrapper pattern

`check_ip_reputation` is a textbook example of an API wrapper. The pattern is
universal across security tooling — VirusTotal, Shodan, GreyNoise, Splunk's
REST API, Sentinel's KQL endpoint, ServiceNow incidents. Same shape every
time:

1. Authenticate (header or query param).
2. Make the request inside a try/except, with a timeout.
3. Check the status code: handle known error cases (auth, rate limit) with
   specific messages; fall through to a generic message for everything else.
4. Parse the JSON response.
5. Reshape into a clean dict with only the fields the caller cares about.

Defensive error handling at the API boundary is non-negotiable. If the tool
crashes, Claude Desktop disconnects from the entire MCP server — losing
access to *both* tools, not just the broken one. Returning a clean error dict
keeps the rest of the system functional.

#### Standalone testing

Three test cases, each chosen deliberately:

| Test | Input | Expected | Result |
|---|---|---|---|
| Known malicious | 185.220.101.42 (Tor exit node) | High abuse score, `is_tor: true` | Score 95, is_tor true, ISP literally "Network for Tor-Exit traffic" ✓ |
| Known benign | 8.8.8.8 (Google DNS) | Score 0 or near zero | Score 0, ISP "Google LLC" ✓ |
| Bad input | `"not-an-ip"` | Clean error dict, no crash | HTTP 422 caught by generic status branch, returned error dict ✓ |

The three cases together prove: malicious IPs are correctly identified, benign
IPs aren't false-flagged, and the tool degrades gracefully on bad input rather
than killing the server.

### Phase 3 — Agent demo

#### Restart procedure

Claude Desktop loads the MCP server as a subprocess at startup. Replacing
`server.py` doesn't update the running subprocess — needed a full restart via
Task Manager (same Microsoft Store sandbox issue from evening 1: the system
tray "Quit" doesn't always actually quit).

After restart, Settings → Developer → Local MCP servers showed `security-tools`
running with the updated tool count.

#### The connector toggle is per-chat

First gotcha: enabling the `security-tools` connector in one chat doesn't
carry over to a new chat. Each chat starts with connectors at default state,
which appears to be "off" for newly-installed local MCP servers.

Diagnosed by sending a "list every tool you have access to" prompt — the
agent's answer revealed which servers were active. Once that distinction was
clear, the fix was to flip the connector toggle on at the start of each new
investigation chat.

For demo purposes, also disabled Google Drive, Indeed, and Claude in Chrome
connectors so the agent's behavior in the recording is clean — every action
has to come from the project's two tools.

#### The non-obvious failure mode: agent vs. tool filesystem

First investigation prompt failed in an interesting way. The prompt referenced
`sample_data/auth.log`. The agent's response: *"No project folder is
accessible to me here... nothing was uploaded to this chat... `/mnt/user-data/
uploads/` has no files."*

The agent didn't even try to call `parse_auth_log`. It reasoned about the
path, concluded it referred to the agent's own sandboxed code-execution
environment (which was empty), and gave up.

This is a real conceptual point worth understanding:

- **Claude has its own sandbox** for the code-execution capability — a
  filesystem at `/mnt/user-data/...` that's separate from the user's machine.
- **MCP servers run as local subprocesses on the user's machine** — they see
  the user's actual filesystem.
- These are two different filesystems. A path can exist in one and not the
  other.

The agent was conflating "I can't see this from my sandbox" with "the MCP
tool can't see this either" — being overly cautious by checking with its
built-in filesystem tools rather than just calling the MCP tool.

#### The fix

Re-prompted with an explicit instruction:

> Call the parse_auth_log tool with this exact absolute path:
> C:\\Users\\pelum\\projects\\mcp-security-tools\\sample_data\\auth.log
>
> This file lives on my local Windows filesystem. The security-tools MCP
> server runs as a subprocess on my machine and can read it. Don't check via
> your built-in filesystem tools — call the MCP tool directly.

After this, the agent correctly:
- Acknowledged its earlier reasoning error explicitly
- Called `parse_auth_log` with the absolute path
- Got the four IPs back
- Called `check_ip_reputation` four times — once per IP
- Synthesized a tiered triage report

#### The output

Better than I expected. The agent produced analyst-level reasoning, not just
data summarization:

- **Critical:** flagged 103.211.18.97 highest priority despite the lowest
  abuse score, because it spotted that `lumi` isn't a generic-wordlist
  username (it's part of `pelumi` — a real account on this box). It correctly
  inferred this is targeted reconnaissance, not opportunistic scanning, and
  noted that a clean abuse score actually makes this *worse* — suggests
  either a careful operator or a freshly-compromised residential proxy.
- **High:** correctly downgraded 185.220.101.42 (the highest-volume attacker)
  from critical because Tor exits hit every internet-facing SSH server
  constantly — "background radiation of the internet."
- **Medium:** identified 45.155.205.233 as opportunistic spray.
- **Low:** noted that 91.240.118.222 should go on a watchlist rather than
  immediate-block — "clean reputation means firewall noise without much
  benefit."

Plus cross-cutting recommendations the agent generated unprompted: fail2ban
tuning with specific values, AllowUsers SSH directive, snapshot the log to
evidence storage before rotation eats the day's data.

#### Honest limitation surfaced

The agent flagged a real gap: `parse_auth_log` only returns failed events, so
it couldn't definitively confirm whether suspicious IPs eventually succeeded.
The agent ended its triage with: *"Tell me what the Accepted-line query
returns and I'll adjust the tiering."*

That's actually the system working correctly — recognizing it needs more data
rather than guessing. Documented in the README's roadmap section as an
intentional v1 scope decision: keep tools narrow so the agent has to chain
queries, which is exactly the pattern production SOC tools require.

### Phase 4 — README, GitHub push

#### README design

Optimized for the fold. First ~150 lines are what a hiring manager scanning
fast actually sees. Demo screenshots above the fold so anyone passing through
sees "this works" before they see "this is what it's for."

No specific company named in the README — framing is generic ("agentic SOC
platforms") so the same artifact serves every application. Targeted framing
goes in interview conversations, not in the public repo.

The Roadmap section explicitly frames the parser limitation as *intentional v1
scope decisions, not bugs*. Hiring managers read roadmap sections to assess
engineering judgment more than to verify completeness — they expect v1 to be
incomplete.

#### Repo hygiene files

- `requirements.txt` via `pip freeze` — pins exact dependency versions for
  reproducibility.
- `.env.example` — template showing required environment variables.
- `LICENSE` (MIT) — standard permissive license; what most portfolio repos use.

#### Git workflow

Standard sequence:

```
git config --global user.name "..."
git config --global user.email "..."
git init
git add .
git status   # verify .env is NOT in the staged list
git branch -m main
git commit -m "Initial commit: ..."
git remote add origin https://github.com/plumi-cyber/mcp-security-tools.git
git push -u origin main
```

The critical safety check: `git status` before any `git commit`, every time.
If `.env` ever appears in the staged list, the `.gitignore` is broken and
committing would expose the API key to history. Cleaning a secret out of Git
history is painful — better to catch it at the staging step.

GitHub created the repo with a capitalized name (`MCP-Security-Tools`) by
default; renamed to lowercase (`mcp-security-tools`) via Settings to match
the convention every other repo in the ecosystem uses.

### Conceptual learnings consolidated (Evening 2)

#### 1. The agent's filesystem is not the same as the tool's filesystem

This was the trickiest concept of the night. AI agents that have code
execution capability run in their own isolated sandbox. MCP servers run as
local subprocesses on the user's machine. Those are two different
filesystems. When you give the agent a path, it has to decide which
filesystem you mean — and may guess wrong.

The fix isn't just "use absolute paths" — it's to make the relationship
between the agent's context and the tool's context explicit in your prompt.
Production agentic systems handle this by binding tools to specific contexts
at registration time so the agent can't get confused.

#### 2. Tool design forces or prevents agent chaining

A tool that returns everything at once short-circuits the agent's reasoning.
A tool that returns one slice forces the agent to run follow-up queries.
SOC platforms deliberately split tools (failures vs. successes, alerts vs.
events, raw logs vs. enriched data) because narrow tools produce more
demonstrable agent reasoning — and easier human auditing.

#### 3. Defensive error handling is the boundary, not the inside

Inside the function, raising an exception is fine — it forces fast feedback
during development. At the boundary (where the function returns to MCP, the
API, the user), exceptions become silent failures of the whole system.
Catch them at the boundary, return clean error dicts, let everything else
keep working.

#### 4. Type hints are a free productivity multiplier

Every type hint you write becomes part of the tool's schema for the AI agent.
Sparse hints → agent uses tools poorly. Rich hints → agent uses tools well.
This shifts the cost-benefit of writing thorough type annotations: in normal
Python they're optional documentation; in MCP servers they're machine-readable
contracts that directly affect agent performance.

#### 5. Connector state is per-chat, not global

A subtle UX detail in Claude Desktop: connector toggles reset per-chat. For
demo recording, this means flipping the toggle on at the start is part of the
visible setup, not a one-time configuration. Easy to forget, hard to debug
("why isn't the agent seeing my tool?") if you don't know.

#### 6. Windows filename extensions are a foot-gun

When File Explorer hides extensions and you rename a file with the extension
visible, you can end up with `.png.png` double extensions silently. Either
turn extensions on (View → Show → File name extensions) or only rename the
base part. The extensions-hidden default is also a security risk — malware
named `invoice.pdf.exe` looks like `invoice.pdf` with extensions hidden.
Worth flipping on for both reasons.

### Troubleshooting reference (Evening 2 additions)

| Symptom | Cause | Fix |
|---|---|---|
| Agent says "no file accessible" when sample_data/auth.log clearly exists | Agent confusing its own sandbox with the MCP server's local filesystem view | Use absolute paths in prompts; explicitly tell the agent to call the MCP tool rather than checking via built-in filesystem tools |
| Connectors menu shows server but no individual tools | Working as designed — Connectors menu is server-level only; tools become visible to the agent once the server toggle is on | Flip the toggle and ask the agent to list its tools in chat to confirm |
| `(Get-Content .env) .Length` PowerShell error | Stray space between `)` and `.Length` | `(Get-Content .env).Length` — flush, no space |
| `(Get-Content .env).Length` returns character count instead of line count | Single-line file: PowerShell returns it as a string (with `.Length` = char count) rather than an array (with `.Length` = line count) | Use `(Get-Content .env).GetType().Name` to check; or use `Select-String -Path .env -Pattern .` to count matching lines |
| Files saving as `.png.png` | File Explorer extensions hidden + manual rename including `.png` | Turn extensions on permanently; rename only base part next time |
| New chat in Claude Desktop ignores tools that worked in previous chat | Connector state is per-chat | Toggle connector on in each new chat, or check Tool access settings |
| `git status` after `git init` shows `master` instead of `main` | Git's default branch name on this machine wasn't updated despite the installer choice | `git branch -m main` to rename before first commit |
| Pasting non-PowerShell content into PowerShell results in "not recognized as cmdlet" errors | Misread file content as command | Use `@'...'@ \| Out-File -FilePath name -Encoding utf8` here-string to write file content from PowerShell |

### What's done

- Two real, tested tools exposed via MCP: `parse_auth_log` and
  `check_ip_reputation`
- Sample data engineered to demonstrate tiered SOC reasoning
- End-to-end agent investigation working
- Public GitHub repo at https://github.com/plumi-cyber/mcp-security-tools
- README optimized for hiring-manager scan
- All secrets correctly excluded from version control
- Build log covering both evenings

### What's left

- Game Bar screen recording of the agent investigation (deferred to next
  morning for lighting and energy reasons)
- Embed the recording in the README via a GitHub release attachment or
  hosted link
- Optional v2 features documented in the README's Roadmap section

### Final architecture diagram

The full picture, after evening 2:

```
┌──────────────────────┐         MCP protocol          ┌─────────────────────────┐
│   Claude Desktop     │ ◄────── (stdio / JSON) ─────► │  server.py              │
│   (MCP client)       │                               │  FastMCP from MCP SDK   │
│                      │                               │                         │
│  - launches server   │   "what tools do you have?"   │  @mcp.tool()            │
│    as subprocess     │                               │  parse_auth_log()       │
│  - reads tool list   │   "call parse_auth_log..."    │       │                 │
│  - lets the AI       │                               │       ▼                 │
│    decide when to    │   "result: {...}"             │   sample_data/auth.log  │
│    call them         │                               │                         │
│                      │   "call check_ip_reputation"  │  @mcp.tool()            │
│                      │                               │  check_ip_reputation()  │
│                      │   "result: {...}"             │       │                 │
└──────────────────────┘                               └───────│─────────────────┘
                                                               ▼
                                                      ┌────────────────────┐
                                                      │  AbuseIPDB API     │
                                                      │  (HTTPS + API key) │
                                                      └────────────────────┘
```

The agent (Claude) sits on the left. The tools sit on the right. MCP is the
protocol slot between them. Each tool reaches out to whatever it needs in
the real world — one to a local file, one to a third-party API.

This is the pattern at the heart of every AI-augmented SOC platform.
Substitute Claude with the platform's agent runtime, substitute the two
tools with dozens of production security integrations, and the architecture
is identical.
