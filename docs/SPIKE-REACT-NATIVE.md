# Spike S42 — React Native shell: notes + feasibility matrix

- **Date:** 2026-10-30 (implements the 10-28 row, late by two days)
- **Status:** Desk-research spike. The lane has NOT scaffolded or run an RN
  app — nothing below is verified on a device. §Verification is the Mac
  recipe that tests the load-bearing claims; STATUS stays
  "DONE (Mac verify pending)" until Carlos runs it.
- **Related:** docs/ADR-001-phase6-hybrid-vs-local-first.md (the chosen hybrid
  shape), docs/PUBLIC-INSTANCE.md (live web shell), S24–S26 (companion +
  bridge), issue #25.

## What a "React Native shell" would wrap

Grounding facts from this repo as of the S41 cut:

- Frontend: React 19 + Vite 8 SPA (`frontend/`), react-router 7, plain CSS
  tokens — no RN or native code anywhere today.
- Transport: JSON REST under `/api/*` + JWT bearer tokens. The SPA keeps the
  token in `localStorage` (`frontend/src/api.ts`) and sends it as an
  `Authorization` header — no cookies, so a WebView does not fight cookie
  SameSite rules.
- Live shell: `http://76.13.122.86:8090` — **plain HTTP on a bare IP**, TLS is
  still an unchecked box in the PUBLIC-INSTANCE hardening list. This is the
  single biggest blocker for any store-bound mobile app (below).
- Training progress is polled (S11/S35), not streamed, so a suspended webview
  just resumes polling on foreground — cheap.
- The Phase 6 plan (ADR-001) says heavy MLX work runs on the Mac via the S24
  companion, which **dials out** to the hub over WebSocket (S25 bridge). A
  phone never needs to reach the Mac directly; it talks to the hub like any
  other client. That assumption is what makes a thin shell viable.

## Options considered

**A. Expo + `react-native-webview` shell.** One `WebView` pointed at the
deployed SPA, plus native sugar (secure token vault, push, share-extension
for dataset import). Rough effort: 1–2 days for an internal demo, days not
weeks. The SPA remains the only UI codebase.

**B. Bare React Native + custom WebView container.** Same shape but we own
the native project (Cocoapods, Gradle), enabling true native modules (keychain
sync, background fetch). Only worth it if Expo Managed hits a wall. Rough
effort: +1–2 weeks of plumbing vs A.

**C. Full native RN UI rewrite.** Rebuild Datasets/Train/Compare/History in
RN components. Duplicates every slice S17+ just shipped on web; the lane
budget cannot carry a second UI. Rough effort: many weeks, permanent twin
maintenance. **Rejected** unless the product itself goes mobile-first.

## Feasibility matrix

| Dimension | A: Expo webview | B: Bare RN webview | C: Native rewrite |
|---|---|---|---|
| Time to first demo | ~1–2 days | ~1 week | ~1 month+ |
| Maintains ONE UI codebase | ✅ | ✅ | ❌ twin UI |
| Fits ADR-001 hybrid (phone = hub client, Mac does MLX) | ✅ | ✅ | ✅ but costly |
| JWT/`Authorization` flow works unchanged | ✅ (webview localStorage) | ✅ + Keychain via native module | ✅ natively |
| iOS ATS: current bare-HTTP `:8090` | ❌ blocked → needs TLS first | ❌ same | ❌ same (API-side, option-independent) |
| App Store review risk | ⚠️ Guideline 4.2 "thin wrapper" rejection risk — must ship real native value (push, share-import, offline badge) | ⚠️ same but easier to prove native depth | low |
| Push notifications | ✅ Expo push (needs native-ish config, TLS) | ✅ | ✅ |
| Offline / flaky network | ❌ webview shows the server's outage; cache only | same as A | ✅ truest |
| Mac/iPad via Catalyst | ✅ free from Managed Typescript | ⚠️ manual | ⚠️ manual |
| New CI surface | `expo export` build; lane can run it headless on VPS | needs macOS runners (Xcode) | needs macOS runners |
| Lane cost per day | near zero | medium | high |

## Risks / open questions found by this spike

1. **TLS is a hard prerequisite for A/B/C alike.** Store builds and iOS ATS
   will not accept `http://IP:8090`. Close the PUBLIC-INSTANCE checklist
   (Caddy/nginx + Let's Encrypt + domain) before any store track. A dev
   simulator can bypass this with an ATS exception; shipping cannot.
2. **Token in webview `localStorage`** is one JS-XSS away from leaking and
   has no biometric gate. Mitigation: keep it for the demo, then move the
   shell to `expo-secure-store`/Keychain and have the webview hand off the
   session (deep-link or injected bridge message).
3. **Guideline 4.2 minimum-functionality.** A pure URL-in-a-frame app gets
   rejected. The honest native story: push on run-finished (pairs with the
   S39-era error explainer), document-picker → dataset upload, and companion
   pairing UI — all hub-API work, no UI duplication.
4. **Bridge reach (S25/S26):** phone → hub is fine; the *Mac companion*
   path is unchanged (it dials out to the hub). No NAT hole needed. Verify
   the hub's consent prompt (§S25) reads sensibly when the request arrives
   from a mobile UA — not yet checked.
5. **Keepalive/dev URLs:** `:8090` is a dev-grade instance; a public app
   on it invites the S15 rate-limit/bind-guard hardening to be exercised
   for real. Fine for a spike, not for store.

## Recommendation (lane's pick, Carlos signs off on #25)

Pursue **A** now as a *private TestFlight demo only*: one Expo project, one
WebView, ATS exception, target `http://76.13.122.86:8090`. Decision gates
before any store effort: (1) TLS checklist closed, (2) at least one shipped
native feature that beats the browser (push on run completion is the cheapest
credible one), (3) token handoff via secure store. Revisit B only when a
required native module is unavailable in Expo Managed. Keep C off the table.

## Verification (Mac recipe — the lane cannot run any of this)

Copy the App.js snippet from the commit body or §snippet below into a fresh
Expo app and run the numbered steps. Success = the LLM Tuner login page
renders inside the iOS simulator and a real login reaches the Datasets list.

1. `xcode-select -p` → expect `/Applications/Xcode.app/Contents/Developer`
   (any recent Xcode; simulator only, no device needed).
2. `node --version` → expect v20 or newer.
3. `mkdir -p ~/spikes && cd ~/spikes && npx create-expo-app@latest llmtuner-shell --template blank`
   → expect a scaffolded project in ~1–3 min.
4. `cd llmtuner-shell && npx expo install react-native-webview expo-secure-store`
   → expect the three packages to install without version warnings.
5. Overwrite `App.js` with the §snippet below, and in `app.json` add the
   dev-only ATS exception: `"ios": {"infoDictionary": {"NSAppTransportSecurity": {"NSAllowsArbitraryLoads": true}}}`.
6. `npx expo start` → expect the QR/menu terminal; press `i` → simulator
   boots (first Metro+iOS build takes a few minutes) and shows the LLM
   Tuner login screen inside the webview.
7. Log in with your own dev account on the instance (do NOT write the
   password into the repo). Expect the SPA to render, theme toggle to
   persist, and Datasets/History pages to work exactly as in Safari.
8. Kill the app in the simulator, relaunch with `npx expo start --clear` →
   expect to stay logged in (webview storage persisted). This is the
   behavior §risk-2 proposes to move to Keychain.
9. Record what broke (blank webview? login 401? mixed-content warning?) as a
   comment on issue #25 — findings replace the desk estimates in the matrix.

### Snippet (App.js, demo-grade)

```jsx
import { View, StyleSheet } from 'react-native';
import { WebView } from 'react-native-webview';

const SHELL_URL = 'http://76.13.122.86:8090'; // dev instance; TLS gates shipping

export default function App() {
  return (
    <View style={styles.root}>
      <WebView
        source={{ uri: SHELL_URL }}
        originWhitelist={['*']}
        style={styles.web}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, paddingTop: 40 },
  web: { flex: 1 },
});
```
