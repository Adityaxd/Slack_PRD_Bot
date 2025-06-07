# Slack PRD Bot

A Slack bot that lets you drop a Product Requirements Document (PRD) into any channel, automatically extracts “shall”-style requirements via OpenAI, shows you a preview, and—on your confirmation—creates one Jira issue per requirement.

---

## Table of Contents

1. [Demo](#demo)  
2. [Features](#features)  
3. [Architecture & Flow](#architecture--flow)  
4. [Tech Stack & Key Libraries](#tech-stack--key-libraries)  
5. [Getting Started](#getting-started)  
   1. [Prerequisites](#prerequisites)  
   2. [Installation](#installation)  
   3. [Configuration](#configuration)  
   4. [Running the Bot](#running-the-bot)  
6. [Project Structure & File Roles](#project-structure--file-roles)  
7. [Design Choices & Algorithms](#design-choices--algorithms)  
8. [Error Handling & Edge Cases](#error-handling--edge-cases)  
9. [Future Improvements](#future-improvements)  
10. [Full Demo Video](#full-demo-video)  
11. [License & Acknowledgements](#license--acknowledgements)  

---

## Demo

1. **Upload** a PDF/DOCX/TXT PRD into Slack.  
2. Bot replies “Processing your document…” then “Found N requirements” with a **Create Jira Tasks** button.  
3. Click the button → Bot creates Jira issues and replies in-thread with clickable issue links.

---

## Features

- **Automatic requirement extraction** via OpenAI (GPT-4o)  
- **Interactive Slack flow** with “Processing…” acknowledgment  
- **Preview** of extracted requirements before Jira creation  
- **One Jira issue per requirement** with summary, description and labels  
- **Custom priority mapping**, assignee, and time-estimate fields  
- **In-memory caching** of analysis results between upload & button click  

---

## Architecture & Flow

Below is the end-to-end sequence showing how a user’s PRD upload flows through Slack, our bot, OpenAI, the in-memory cache, Jira integration, and back into Slack:

![Slack PRD Bot System Overview](Slack_PRD_Bot.png)

```plantuml
@startuml
title Slack PRD Bot System Overview

skinparam packageStyle rectangle
skinparam rectangle {
  BackgroundColor<<Slack>>  #D0E6FF
  BackgroundColor<<Server>> #F0F0F0
  BackgroundColor<<AI>>     #E0F4E0
  BackgroundColor<<Jira>>   #F4E0E0
}

actor User <<Slack>>

package "Slack Workspace" <<Slack>> {
  participant "Slack Events API" as Events
  participant "Slack PRD Bot"    as Bot
}

package "Bot Server" <<Server>> {
  participant "Document Parser\n(pdfplumber/docx)" as Parser
  participant "Analyzer\n(analyze_document)"     as Analyzer
  participant "In-Memory Cache\n(cache_key→requirements)" as Cache
}

rectangle "OpenAI API" <<AI>> as OpenAI

package "Jira Cloud" <<Jira>> {
  participant "Jira Integration" as JiraInt
  participant "Jira REST API"    as JiraAPI
}

== Upload & Parse ==
User -> Events : upload PRD file
Events -> Bot  : file_share event\n(payload)
Bot -> Parser  : download file bytes
Parser -> Parser : extract raw text

== Analyze ==
Bot -> Bot      : send "Processing your document…"
Bot -> Analyzer : provide raw text
Analyzer -> OpenAI : prompt (system + document_text)
OpenAI -> Analyzer : JSON requirements response
Analyzer -> Cache    : store latest analysis
Bot <- Analyzer : "Found X requirements"

== Create Jira Tasks ==
User -> Bot      : click "Create Jira Tasks"
Bot -> Cache     : fetch last analysis
Bot -> JiraInt   : create issues for each req
JiraInt -> JiraAPI : POST /rest/api/3/issue
JiraAPI -> JiraInt  : issueKey + URL
JiraInt -> Bot      : return created links
Bot -> Bot       : post thread reply with links

@enduml

Tech Stack & Key Libraries

    Language: Python 3.10+

    Slack integration: slack-bolt

    PDF parsing: pdfplumber

    DOCX parsing: python-docx

    LLM calls: OpenAI Python SDK (GPT-4o)

    Jira integration: requests + Jira Cloud REST API

    Data modeling & validation: Pydantic

    In-memory cache: Python dict (per-instance)

Getting Started
Prerequisites

    Python 3.10 or higher

    A Slack App with Bot Token & Signing Secret

    OpenAI API Key

    Jira Cloud account + API Token + target Project Key

Installation

git clone https://github.com/your-org/Slack_PRD_Bot.git
cd Slack_PRD_Bot
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
.\.venv\Scripts\activate         # Windows PowerShell
pip install -r requirements.txt

Configuration

Copy .env.example to .env and fill in:

SLACK_BOT_TOKEN= xoxb-...
SLACK_SIGNING_SECRET= ...
OPENAI_API_KEY= sk-...
JIRA_URL= https://your-domain.atlassian.net
JIRA_EMAIL= your.email@example.com
JIRA_API_TOKEN= ...
JIRA_PROJECT_KEY= SCRUM

Running the Bot

python app.py

Project Structure & File Roles

bot/
├── __init__.py           # (empty) package marker
├── config.py             # Loads env vars into Config.*
├── analysis.py           # extract_text + analyze_document logic
├── jira_integration.py   # create_jira_tasks(requirements)
└── slack_handlers.py     # Slack event & action listeners + in-memory cache
app.py                    # Bootstraps Bolt App and registers handlers
requirements.txt          # pinned dependencies
README.md                 # ← This document

    config.py
    Centralizes credentials & URLs as a Pydantic settings model.

    analysis.py

        extract_text(file_bytes, filename)

        analyze_with_openai(text) & analyze_document(...)
        Sends system+user prompt to OpenAI, parses JSON into Pydantic models.

    slack_handlers.py

        handle_file_shared_event: listens for file uploads, acknowledges “Processing…”, downloads file, invokes analyze_document(), caches results, posts preview + button.

        handle_create_tasks: on button click, retrieves cached requirements, calls Jira integration, replies with issue links.

    jira_integration.py

        create_jira_tasks(requirements): maps PRD priorities, builds ADF description, posts to Jira API, handles rate-limits & errors, returns keys & URLs.

Design Choices & Algorithms

    Prompt Engineering

        Expert Business Analyst system prompt to ensure context-aware extraction.

        Low temperature (0.1) for deterministic outputs.

    In-Memory Cache

        UUID Keying: every upload generates uuid4() key.

        Transient Storage: no external DB—everything lives in RAM until restart.

    Modular Separation

        Single-Responsibility files (analysis, Jira integration, handlers).

        Pydantic Models validate every requirement against a strict schema.

    Error Resilience

        Rate-Limit Retries: automatic back-off on 429 from Jira.

        File Fallbacks: PDF → DOCX → plain-text.

        User-Friendly Messaging: clear Slack thread notifications on errors.

Error Handling & Edge Cases

    Malformed PRDs → “Found 0 requirements” + still shows button

    OpenAI JSON parse failure → logged & user notified

    Jira API errors → per-requirement logs, then abort with thread notification

    Cache misses (button clicked after restart) → empty list & user informed

Future Improvements

    Persistent cache with Redis to survive restarts

    Support .md/.html via markdown parser

    Configurable Slack channels & Epics per upload command

    Batching of Jira API calls and better back-pressure

    Unit & integration tests for CI/CD

    Dockerization for one-click deployment

Full Demo Video

For a full, comprehensive walkthrough of the bot in action, check out this video:

▶️ Full Comprehensive Demo for the Bot
License & Acknowledgements

© 2025 Aditya Chaudhary
Built with ☕ Python, 🤖 OpenAI, and 🐍 community libraries.
