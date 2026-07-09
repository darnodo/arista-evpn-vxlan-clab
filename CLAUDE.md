# CLAUDE.md

## Project context

Arista **EVPN/VXLAN** network lab built on Containerlab + cEOS, simulating three
interconnected zones:

- **DC** (Data Center): 2 spines, 8 leafs (4 MLAG/VTEP pairs), 2 MLAG border leafs, 4 access switches, 4 hosts
- **Core**: 2 L3 transit routers (iBGP AS 65500, OSPF underlay)
- **Campus**: 2 spines, 4 leafs (2 MLAG/VTEP pairs), 2 MLAG border leafs, 2 access switches, 2 hosts

A `gold` VRF is stretched end-to-end between DC and Campus through the Core (EVPN
Type-5, stitched over eBGP IPv4 on the Core).

Source of truth repo: `https://gitea.arnodo.fr/Damien/arista-evpn-vxlan-clab`

## Naming convention

- Hostname format: `<area>-<role><n>` where `area` ∈ `{dc, campus, core}`
- Examples: `dc-leaf1`, `campus-border-leaf2`, `core1`
- This convention is used as-is for IPFabric site separation
  (regex: `^(dc|campus|core)-?.*$`)

## Repository structure

- `README.md` — overview, IP addressing, VNI mapping, control plane, quickstart
- `TROUBLESHOOTING.md` — diagnostic procedures
- `END_TO_END_TESTING.md` — end-to-end test scenarios
- `evpn-lab.clab.yml` — Containerlab topology definition
- `configs/` — Arista EOS configs per node (`<hostname>.cfg`)
- `hosts/` — network configuration for simulated Linux hosts
- `assets/` — diagrams (drawio/svg)

## Tech stack

- **Containerlab** for topology orchestration
- **cEOS** (containerized Arista EOS) as the network OS
- **IPFabric** for network assurance and site separation
- **Gitea** (self-hosted, `gitea.arnodo.fr`) as the source of truth

## GitOps workflow — mandatory rule

**Every action on this project must be tracked by a Gitea issue.**

- Before starting any work (config change, topology addition, documentation, etc.),
  confirm an **issue exists** and reference it in commits (`Refs #<n>` or `Closes #<n>`).
- If no issue covers the identified need: **create the issue first**, describe the
  problem/requirement, and only then act on it.
- No TODO should ever be left "floating" in code, commits, or discussions: it's
  either already an issue, or it must become one immediately.
- This `CLAUDE.md` file stays **general**: it must never contain one-off tasks.
  Action details live exclusively in issues.

## Style guidelines

- Be concise and direct — no filler, no unnecessary preamble
- Issues: short title, straight to the point description (context, expected outcome, no fluff)
- Commit messages: short, factual, imperative mood
- Documentation (README, TROUBLESHOOTING, etc.): technical and dense — tables over
  prose, no marketing tone, no redundant explanations
- Avoid restating what's already documented elsewhere — link/reference instead of duplicating

## Contribution conventions

- Atomic commits, clear message, reference to the associated issue
- Any Arista config change must stay consistent with the IP addressing / VNI / RD
  tables documented in `README.md`
- Any topology change (`evpn-lab.clab.yml`) must be reflected in `assets/` (diagram)
  and in the `README.md` tables
- New validation procedures go in `END_TO_END_TESTING.md`; known issues go in
  `TROUBLESHOOTING.md`

## Default behavior for Claude

1. Before any action, identify the corresponding Gitea issue (or create one first)
2. Stay within the scope of the issue being worked on — don't drift to other topics
3. Strictly follow the `<area>-<role><n>` naming convention
4. Never introduce hardcoded TODO/FIXME in repo files — always go through an issue
