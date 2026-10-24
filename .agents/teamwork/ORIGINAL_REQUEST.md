# Original User Request

## Initial Request — 2026-10-23T22:37:47Z

Requested team: A team of four agents:
1. One agent will be going to Google Maps Pro and will be scraping the data from Google Maps for the various states of the USA. The niche will be roofers who don't have websites.
2. The second agent will take the data from agent one and paste it into the same Google Sheet.
3. The third agent's work will be to make a personalized message for each business, for each store.
4. The fourth agent's work will be to send personalized outreach in a humanized form to every business by email or WhatsApp.

An automated 4-agent pipeline that discovers roofing contractors across US states on Google Maps who lack a website, streams verified leads into a central Google Sheet CRM, drafts bespoke personalized value propositions, and delivers humanized outreach via Email with WhatsApp fallback using a staged review safety system.

Working directory: ~/teamwork_projects/roofer_outreach_pipeline
Integrity mode: development

Target Google Sheet ID: 12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY (Tab: Leads Tracker)

## Requirements

### R1. Google Maps Extraction Engine (Agent 1)
Search Google Maps across target US states (e.g., Texas, Florida, Ohio, Georgia, Arizona) for roofing companies, filtering strictly for active contractors who have no listed website URL (or only social/directory pages). Extract:
- Business name
- Cleaned phone number
- City, State, and ZIP code
- Review count and star rating
- Primary service specialty (residential, commercial, storm repair, leak repair)

### R2. Google Sheets CRM Ingestion & Deduplication (Agent 2)
Append new extracted leads into the Leads Tracker tab of Google Sheet 12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY:
- Preserve existing rows and adhere to column schema (Lead Status, Priority, Company Name, Website, Industry / Niche, Phone / Work Email, Location, Personalized Icebreaker, Offer Angle).
- Deduplicate by normalized business name and phone number so no contractor is added twice.
- Set initial status to Not Contacted and assign lead score priority (🔥 High for >10 reviews without a website).

### R3. AI Personalization & Hook Generator (Agent 3)
For each new roofer in the sheet, generate a custom 2-sentence icebreaker and a specific revenue pain-point angle:
- Reference their exact city/metro and specific service specialty.
- Highlight the revenue lost to local competitors ranking on Google Maps and organic search for emergency roof repairs.
- Store the drafted email subject, email body, and pre-formatted WhatsApp message directly into dedicated staging columns.

### R4. Humanized Outreach Dispatch with Staged Approval (Agent 4)
Implement an outreach dispatch engine:
- Default to Staged Approval Mode: messages remain in status Drafted / Ready for Review until approved.
- When triggered to send, deliver personalized Cold Email as primary channel, with fallback pre-populated WhatsApp click-to-chat links (https://wa.me/<phone>?text=<encoded_msg>).
- Enforce humanized sending pacing (randomized 45–180 second delays between outbound emails, configurable daily send caps) to protect sender reputation.
- Automatically update Lead Status to Contacted (Touch 1) and record the Touch 1 Date in the sheet upon dispatch.

## Acceptance Criteria

### Extraction & Filtering Accuracy
- [ ] Automated scraper query reliably discovers at least 25 distinct roofing businesses in target US regions with confirmed missing website fields.
- [ ] No contractor with a functioning custom domain (.com, .io, .net, .co) is marked as "No Website".

### CRM Integrity
- [ ] Extracted leads populate columns A through U without shifting or corrupting existing header formulas or dashboard KPI cells.
- [ ] Re-running the pipeline on the same geographic area yields zero duplicate rows in the sheet.

### Personalization Quality
- [ ] 100% of generated icebreakers mention the contractor's specific city and trade niche.
- [ ] Personalization does not output placeholder tags like {{City}} or {{Name}} into final staging cells.

### Operational Safety & Dispatch
- [ ] System operates safely in Staged Review mode without dispatching live emails without user confirmation.
- [ ] Sending simulator/dry-run confirms randomized delays between consecutive dispatches.


## Follow-up � 2026-10-24T15:05:06Z

The user has requested to continue the remaining pipeline work. All background processes were paused due to a server restart. Please revive execution, check the orchestrator status in C:\Users\rishi\teamwork_projects\roofer_outreach_pipeline\.agents\teamwork\orchestrator_1, resume gate evaluation for Milestone 2, and drive completion through Milestone 3 (AI Personalization) and Milestone 4 (Outreach Dispatch) to the final audit.
