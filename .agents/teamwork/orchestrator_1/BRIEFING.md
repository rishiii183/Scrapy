# BRIEFING — 2026-10-23T22:40:00Z

## Mission
Orchestrate and deliver the Roofer Outreach Pipeline: an automated 4-agent system for Google Maps extraction of website-less roofers, Google Sheets CRM deduplication, AI personalization, and staged outreach dispatch.

## 🔒 My Identity
- Archetype: orchestrator
- Roles: orchestrator, user_liaison, human_reporter, successor
- Working directory: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\orchestrator_1
- Original parent: sentinel
- Original parent conversation ID: 1bf34eef-102c-4398-9012-f83eb47f7254

## 🔒 My Workflow
- **Pattern**: Project Pattern
- **Scope document**: C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\PROJECT.md
1. **Decompose**: Survey full scope with 3 Explorers, create PROJECT.md with architecture, feature inventory, milestone breakdown, and interface contracts.
2. **Dispatch & Execute**:
   - Direct / Delegate: Delegate milestones to sub-orchestrators and run E2E testing track in parallel.
   - Iteration loop: Explorer -> Worker -> Reviewer -> Challenger -> Auditor -> Gate check.
3. **On failure**:
   - Retry: nudge or re-send task
   - Replace: spawn fresh agent from interruption point
   - Skip: proceed without (if non-critical)
   - Redistribute: split remaining tasks
   - Redesign: re-partition decomposition
   - Escalate: Project Orchestrator has no parent for escalation; redesign on failure.
4. **Succession**: At 16 spawns, write handoff.md, cancel timers, spawn successor.
- **Work items**:
  1. Survey & Scope Mapping [in-progress]
  2. E2E Testing Track [pending]
  3. Milestone 1: Google Maps Extraction Engine [pending]
  4. Milestone 2: Google Sheets CRM Ingestion & Deduplication [pending]
  5. Milestone 3: AI Personalization & Hook Generator [pending]
  6. Milestone 4: Humanized Outreach Dispatch with Staged Approval [pending]
  7. Final Milestone: 100% E2E test pass + adversarial coverage hardening [pending]
- **Current phase**: 0 (Survey)
- **Current focus**: Launching Survey with 3 Explorers

## 🔒 Key Constraints
- NEVER write, modify, or create source code files directly.
- NEVER run build/test commands yourself — require workers to do so.
- NEVER investigate or explore the problem at the code level — dispatch Explorers for technical investigation.
- Use file-editing tools ONLY for metadata/state files (.md) in .agents/teamwork/ or PROJECT.md.
- Forensic Auditor verdict is a BINARY VETO (no exceptions).
- Always include path to ORIGINAL_REQUEST.md in subagent dispatches.
- Never reuse a subagent after handoff delivery — always spawn fresh.

## Current Parent
- Conversation ID: 1bf34eef-102c-4398-9012-f83eb47f7254
- Updated: 2026-10-23T22:39:22Z

## Key Decisions Made
- Selected Project Pattern with Dual Track (Implementation + E2E Testing).
- Survey phase initiated with 3 parallel Explorers.

## Team Roster
| Agent | Type | Work Item | Status | Conv ID |
|-------|------|-----------|--------|---------|
| explorer_survey_1 | teamwork_preview_explorer | Survey Maps Extraction & Environment | completed | 38f96d3e-7fdb-41ad-b009-835a9671125b |
| explorer_survey_2 | teamwork_preview_explorer | Survey CRM & Google Sheets | completed | 5065024c-0a92-4e4e-ae3e-46506964be53 |
| explorer_survey_3 | teamwork_preview_explorer | Survey Personalization & Outreach | completed | ff6f0d5b-3562-4d91-b6ab-c0431e5fb590 |
| test_writer_e2e | teamwork_preview_test_writer | E2E Testing Suite (Tiers 1-4) | completed (TEST_READY.md published) | 72dd1137-b698-4be6-bd8b-6cec050f661c |
| worker_m1 | teamwork_preview_worker | Milestone 1: Maps Scraper Implementation | completed | 06c4e5f5-6cab-41db-8976-92cefde534ce |
| reviewer_m1_1 | teamwork_preview_reviewer | M1 Review: Code & Interface | completed (APPROVE) | 2788991c-bcd8-4138-a75a-aff2c40d0434 |
| reviewer_m1_2 | teamwork_preview_reviewer | M1 Review: Robustness & anti-bot | completed (APPROVE) | 692f039f-4ab0-40fa-9fa9-57bb72718425 |
| challenger_m1_1 | teamwork_preview_challenger | M1 Challenge: Website & Phone | completed (REQUEST_CHANGES) | 7319c682-93c7-4e30-ac30-ef78d93efc1e |
| challenger_m1_2 | teamwork_preview_challenger | M1 Challenge: Cards, SAB & Dedup | completed (REQUEST_CHANGES) | 06773599-8b55-4444-aa71-0d8116efb098 |
| auditor_m1_1 | teamwork_preview_auditor | M1 Forensic Integrity Audit | completed (CLEAN) | a62a963b-c5e4-4aed-a748-77f120434429 |
| explorer_m1_r2_1 | teamwork_preview_explorer | M1 R2: URL & Phone Fix Strategy | completed | 000032c0-d46f-4c33-b4f0-0280f0115120 |
| explorer_m1_r2_2 | teamwork_preview_explorer | M1 R2: Area Code & Dedup Strategy | completed | 99ab52aa-05a3-4960-a654-c2edf45d9d83 |
| explorer_m1_r2_3 | teamwork_preview_explorer | M1 R2: PLLC & Validation Strategy | completed | 1ae7b732-d276-4fe2-9946-943c26f23613 |
| worker_m1_r2 | teamwork_preview_worker | M1 R2: Apply Challenger Fixes | completed | 9dd32a80-3a3d-4a9f-b0d0-7174aee057e0 |
| reviewer_m1_r2 | teamwork_preview_reviewer | M1 R2 Verification | completed (APPROVE) | ee409a89-8760-46d7-9805-5509e4c9683f |
| challenger_m1_r2 | teamwork_preview_challenger | M1 R2 Verification | completed (APPROVE) | c60e48b8-d0ed-483d-9acf-5eae3a35b92d |
| worker_m2 | teamwork_preview_worker | Milestone 2: Sheets CRM & Dedup | completed | d3430cf1-c3a3-45d6-b465-b7fbefe92c71 |
| reviewer_m2_1 | teamwork_preview_reviewer | M2 Review: Schema & Client | completed (APPROVE) | 1cfb5f86-8c16-4c4c-8621-911f3bc313af |
| reviewer_m2_2 | teamwork_preview_reviewer | M2 Review: Dedup & Ingestor | completed (APPROVE) | 3a5627cd-0cdd-44e7-9993-95f5a685e137 |
| challenger_m2_1 | teamwork_preview_challenger | M2 Challenge: Dedup Stress | completed (REQUEST_CHANGES) | 8e630ca0-8584-442d-91cb-86d52fc26891 |
| challenger_m2_2 | teamwork_preview_challenger | M2 Challenge: Schema Stress | completed (APPROVE) | ae5ee5f8-0090-4838-adbe-1bee08b67885 |
| auditor_m2_1 | teamwork_preview_auditor | M2 Forensic Integrity Audit | completed (CLEAN) | ede91ffe-63bf-46d9-ad65-9b2517ff5a09 |
| worker_m2_r2 | teamwork_preview_worker | M2 R2: Dedup Phone Extension Fix | completed | 2f0efcbd-8e1d-455a-b260-25eec6d6ea52 |
| worker_m3 | teamwork_preview_worker | Milestone 3: AI Personalization | completed | 30622cf9-f328-4861-a583-597a953e4497 |
| reviewer_m3_1 | teamwork_preview_reviewer | M3 Review: Code & Architecture | completed (APPROVE) | b0d5b9fe-2936-409f-a41d-9d807f12cea9 |
| reviewer_m3_2 | teamwork_preview_reviewer | M3 Review: Invariants & Copy | completed (APPROVE) | 4be9f6c5-088a-4ab6-b14b-2f15ed8f52d1 |
| challenger_m3_1 | teamwork_preview_challenger | M3 Challenge: Personalization Stress | completed (APPROVE) | a6f42fc3-ecbe-427b-9a84-4cba15a5b5cf |
| challenger_m3_2 | teamwork_preview_challenger | M3 Challenge: WhatsApp & LLM Resilience | completed (REQUEST_CHANGES) | a26ae955-ebac-4fc5-a493-3027912957a7 |
| auditor_m3_1 | teamwork_preview_auditor | M3 Forensic Integrity Audit | completed (CLEAN) | a63eb14d-5016-4025-a3d1-cb3a2e7a327c |
| worker_m3_r2 | teamwork_preview_worker | M3 R2: WhatsApp Phone Extension Fix | completed | c1541806-627d-441c-b1be-edde96e30e07 |
| reviewer_m3_r2 | teamwork_preview_reviewer | M3 R2 Verification | completed (APPROVE) | c555b0bf-496b-4dfe-adea-c0a72daff485 |
| challenger_m3_r2 | teamwork_preview_challenger | M3 R2 Verification | completed (APPROVE) | 8ad8d831-3b0f-4d8c-a3ac-3cea28e082e8 |
| worker_m4 | teamwork_preview_worker | Milestone 4: Outreach Dispatcher & CLI | in-progress | 516db94f-583a-4135-af06-ec22489e595c |

## Succession Status
- Succession required: no
- Spawn count: 33
- Pending subagents: 516db94f-583a-4135-af06-ec22489e595c
- Predecessor: none
- Successor: none (single-orchestrator execution)

## Active Timers
- Heartbeat cron: ea620b15-fa32-4ce7-8b6f-715d76d0d59b/task-383
- Safety timer: worker_m3 safety timer
- On succession: kill all timers before spawning successor
- On context truncation: run manage_task(Action="list") — re-create if missing

## Artifact Index
- C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\ORIGINAL_REQUEST.md — Authoritative user requirements
- C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\orchestrator_1\DISPATCH.md — Task assignment from Sentinel
