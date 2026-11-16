# Rewrite for Server 58+ REST Gateway Architecture and Drop S1–S57 Dual-Protocol

Status: accepted

Server 58 (`http://sg58.dipan.com/`) replaces the legacy ASP.NET WebForms `/GateWay/*.ashx` stack with a REST `/api/*` backend, `Optimization.ashx` batch endpoints, and `/api/notify/history` (removing `SGWebIM.swf` XMLSocket chat), returning `ret=1` or incompatible schemas on legacy endpoints (`Common.ashx?id=29/32/76/77/27`, `City.ashx?id=7/50`, `Map.ashx?id=6`, `OPT.ashx?id=65`, `Common.ashx?id=24`).

We decided to rewrite `GatewayClient` and all client-side automation modules exclusively for Server 58+ (dropping S1–S57 dual-protocol fallbacks), auto-resolve `userId` from session cookies, parse JSON error payloads on HTTP `400`, keep client-side automation rather than delegating to server-side `/api/assistant/*`, and store full API samples in [docs/api/server58-reference.md](../api/server58-reference.md).

- **Considered Options**:
  - *Dual-protocol runtime detection (S1–S57 + S58)*: Rejected because `City.ashx?id=7`, `Common.ashx?id=77`, `Map.ashx?id=6`, and `Common.ashx?id=20` diverge structurally (field swaps, `list[i][2] = map_id`, `city[3] = user_id`), making dual maintenance error-prone.
  - *Wrapping server-side `/api/assistant/*`*: Rejected so existing per-feature client automation, multi-base coordination, and battle tactics keep working with full observability.
- **Consequences**:
  - Version bumped to `2.0.0`; versions `>= 2.0.0` are intentionally incompatible with legacy S1–S57 servers.
  - `Scanner` capital detection now uses `infos` tile `cmid` and `size >= 4` (`THIEN_THANH_MIN_LEVEL = 4`).
  - `WorldChatClient` polls `/api/notify/history` instead of opening an XMLSocket connection.
