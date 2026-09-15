import json, urllib.request, urllib.error, pathlib

T = None
for line in pathlib.Path("/home/hermes/secrets/github.env").read_text().splitlines():
    if line.startswith("export GITHUB_TOKEN"):
        T = line.split('="', 1)[1].rstrip('"')
API = "https://api.github.com/repos/lecharles/llm-fine-tuner-agent-tester"

def req(method, url, body=None):
    r = urllib.request.Request(url, method=method,
        headers={"Authorization": f"Bearer {T}", "Accept": "application/vnd.github+json"},
        data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(r) as resp:
            d = resp.read().decode()
            return resp.status, (json.loads(d) if d else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:150]

def ensure_labels():
    want = {"feature":"4EDECF","infra":"BFD4F2","release":"E4E6C3",
            "lower-hanging-fruit":"F9D0C4","intermediate":"C2E0C6","advanced-feature":"FBC4FF",
            "phase5":"7AE1E1","phase6":"FEDBB4","backlog":"FFFFF0"}
    have = {l["name"] for l in req("GET", API+"/labels?per_page=100")[1]}
    for n,c in want.items():
        if n not in have:
            print("label+", n, req("POST", API+"/labels", {"name":n,"color":c})[0])

def milestone(title, due):
    for m in req("GET", API+"/milestones?state=open")[1]:
        if m["title"] == title: return m["number"]
    s, r = req("POST", API+"/milestones", {"title":title, "due_on":due})
    return r["number"] if s == 201 else None

def relabel_existing(V1):
    fix = {**{i:["bug"] for i in range(1,6)}, **{i:["feature"] for i in range(6,19)}, 19:["infra"], 20:["infra"]}
    diff = {1:"intermediate",2:"intermediate",3:"lower-hanging-fruit",4:"intermediate",5:"intermediate",
            6:"intermediate",7:"intermediate",8:"lower-hanging-fruit",9:"intermediate",10:"lower-hanging-fruit",
            11:"intermediate",12:"intermediate",13:"intermediate",14:"intermediate",15:"lower-hanging-fruit",
            16:"lower-hanging-fruit",17:"intermediate",18:"intermediate",19:"intermediate",20:"lower-hanging-fruit"}
    for i in range(1,21):
        code, iss = req("GET", f"{API}/issues/{i}")
        if code != 200: continue
        prio = [l["name"] for l in iss["labels"] if l["name"].startswith("priority:")]
        new = fix[i] + prio + [diff[i]] + (["release"] if i==18 else [])
        if {l["name"] for l in iss["labels"]} != set(new):
            print("relabel", i, req("PUT", f"{API}/issues/{i}/labels", {"labels": new})[0])
        if iss.get("milestone") is None and V1:
            print("milestone", i, req("PATCH", f"{API}/issues/{i}", {"milestone": V1})[0])

NEW = [
 ("Phase 5: theme pass + styled components (theme.css, ConfirmDialog, VU-meter loader, iters input)", ["feature","phase5","intermediate","priority:medium"], "V2", "S17 10-01 / S18 10-02", "ROADMAP Phase 5. Apply the parked design system over the finished app; ConfirmDialog replaces temp no-confirm delete; Thinking/VU-meter loading indicator; nicer iters input; cleaner status labels."),
 ("Phase 5: accessibility pass (WCAG AA contrast, alt text, link-based navigation)", ["feature","phase5","intermediate","priority:medium"], "V2", "S19 10-05", "ROADMAP Phase 5. Accessibility pass over the themed app."),
 ("Phase 5: logged-in user display + user menu via GET /api/auth/me", ["feature","phase5","lower-hanging-fruit"], "V2", "S20 10-06", "ROADMAP Phase 5. Current user in nav, logout in a small Linear-style user menu."),
 ("Phase 5: deploy the web shell online (training stays local)", ["feature","phase5","advanced-feature","priority:medium"], "V2", "S21 10-07", "ROADMAP Phase 5. Public web shell; Apple Silicon training remains on-device."),
 ("Phase 6 ADR: hybrid (web shell + local companion) vs full local-first", ["infra","phase6","advanced-feature","priority:medium"], "V2", "S22 10-08", "ROADMAP Phase 6. Architecture decision record; unblocks installer, companion, bridge, split."),
 ("Phase 6: macOS installer (one command or one file)", ["feature","phase6","advanced-feature"], "V2", "S23 10-09", "ROADMAP Phase 6. Places the local runtime on the user's Mac."),
 ("Phase 6: local companion runtime (train, fuse, export, serve driven by web requests)", ["feature","phase6","advanced-feature"], "V2", "S24 10-12", "ROADMAP Phase 6."),
 ("Phase 6: opt-in hardware bridge (explicit, scoped, revocable permission)", ["feature","phase6","intermediate"], "V2", "S25 10-13", "ROADMAP Phase 6. Accept-prompt before the hosted app uses local hardware."),
 ("Phase 6: data model split (local artifacts vs hosted account/metadata)", ["infra","phase6","advanced-feature"], "V2", "S26 10-14", "ROADMAP Phase 6. Memory, models, training artifacts stay local."),
 ("Phase 6: fluid end-to-end path from fresh install (no terminal)", ["feature","phase6","advanced-feature"], "V2", "post-S26", "ROADMAP Phase 6. Sign in, dataset, train, export, compare without a terminal."),
 ("Generation UX: auto-fill use-case prompt from dataset name/description", ["feature","lower-hanging-fruit"], "V2", "S27 10-15", "ROADMAP Generation and dataset UX. Editable, non-destructive draft when prompt is empty."),
 ("Compare: parallelize four-way fan-out", ["feature","intermediate"], "V2", "S28 10-16", "ROADMAP Compare chat depth. Concurrent backend calls to cut latency."),
 ("Training error explainer (LLM plain-language failure summaries)", ["feature","advanced-feature","backlog"], "BL", "backlog", "ROADMAP Training error explainer. Plain-language explanation instead of traceback; post-MVP differentiator."),
 ("Sharing: public/private datasets and models + owner-or-public read auth", ["feature","intermediate","backlog"], "BL", "backlog", "ROADMAP Sharing and visibility. is_public flags; reads owner-or-public, writes owner-only."),
 ("Advanced training mode (hyperparameter panel via advanced_config JSON)", ["feature","advanced-feature","backlog"], "BL", "backlog", "ROADMAP Backlog. Method, lr, rank, alpha, dropout, batch, grad checkpointing; iters stays the simple default."),
 ("Training run visibility: overview + history view", ["feature","intermediate","backlog"], "BL", "backlog", "ROADMAP Backlog. Queued/running/completed/failed scannable; Current Run and History tabs."),
 ("Brand pass: guitar-tuner motif, Swagger UI theming, light/dark mode", ["feature","lower-hanging-fruit","backlog"], "BL", "backlog", "ROADMAP Brand and design."),
 ("In-app guides: fine-tuning, dataset design, hyperparameters, export, testing", ["feature","intermediate","backlog"], "BL", "backlog", "ROADMAP Product depth."),
 ("More model families beyond Llama 3.2", ["feature","advanced-feature","backlog"], "BL", "backlog", "ROADMAP Product depth."),
 ("Repo extraction: API Agents + API Infrastructure showcase repos", ["infra","advanced-feature","backlog"], "BL", "backlog", "ROADMAP Repo strategy. Flagship stays; SDK surface and enterprise controls get dedicated repos."),
 ("Platform expansion: React Native, native macOS, Swift refactor", ["infra","advanced-feature","backlog"], "BL", "backlog", "ROADMAP Platform expansion. Long horizon, parked deliberately."),
]

def create_new(V2, BL):
    existing, page = set(), 1
    while True:
        s, iss = req("GET", f"{API}/issues?state=all&per_page=100&page={page}")
        if s != 200 or not iss: break
        existing.update(i["title"].split("(")[0].strip() for i in iss if "pull_request" not in i)
        if len(iss) < 100: break
        page += 1
    ms = {"V2": V2, "BL": BL}
    for title, labels, m, slice_, desc in NEW:
        if title.split("(")[0].strip() in existing:
            print("exists:", title[:40]); continue
        body = f"**From `docs/ROADMAP.md`.**\n\n{desc}\n\n**Planned commit-train slice:** {slice_}"
        s, r = req("POST", API+"/issues", {"title": title, "body": body, "labels": labels, "milestone": ms[m]})
        print("issue+", r["number"] if s==201 else r, title[:45])

def comment1():
    s, iss = req("GET", f"{API}/issues/1")
    if s != 200: return
    body = ("Lane findings 09-15:\n"
            "- Current bundle already sends form-encoded `URLSearchParams` for login; backend returns 200 + JWT for a plain form POST.\n"
            "- Reproduced twice: the identical POST *with* an `Origin:` header hangs the :8090 process (curl stalls until timeout). Browsers always send Origin; plain curl does not. Suspect a request-path stall for browser-style requests, not the old JSON-vs-form theory.\n"
            "- Next: restart :8090 from current HEAD, A/B test with/without Origin, then browser verify. Details in docs/COMMIT-TRAIN.md row H1.")
    print("comment #1:", req("POST", f"{API}/issues/1/comments", {"body": body})[0])

# write probe first
s, r = req("POST", API+"/issues/1/comments", {"body": "write-probe: fine-grained token permissions check (ignore, replaced by findings comment)"})
print("WRITE PROBE:", s if s in (201,) else r)
if s != 201:
    raise SystemExit("blocked: Issues permission is read-only on this token")
V1 = milestone("v0.1.0", "2026-09-30T00:00:00Z")
V2 = milestone("v0.2.0", "2026-10-31T00:00:00Z")
BL = milestone("Backlog", None)
print("milestones:", V1, V2, BL)
ensure_labels()
relabel_existing(V1)
create_new(V2, BL)
print("SYNC COMPLETE")
