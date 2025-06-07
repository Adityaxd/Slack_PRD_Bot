# bot/jira_integration.py

import time
import random
import logging
from typing import List, Dict

import requests
from requests.auth import HTTPBasicAuth

from bot.config import Config

logger = logging.getLogger(__name__)


# Map PRD priorities to Jira priorities # (Jira has "High", "Medium", "Low" but PRD uses "Critical", "Major", "Minor")
_PRIORITY_MAPPING = {
    "Critical": "High",
    "Major":    "Medium",
    "Minor":    "Low"
}


def format_adf_description(text: str) -> Dict:
    """
    Wrap plain text into a minimal Atlassian Document Format (ADF) paragraph.
    """
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}]
            }
        ]
    }


def create_jira_tasks(requirements: List[Dict]) -> List[Dict]:
    """
    Given a list of requirement dicts, create Jira issues for each and return list of
    {requirement_id, jira_key, jira_url}.
    """
    jira_url = (Config.JIRA_URL or "").rstrip("/")
    url = f"{jira_url}/rest/api/3/issue"
    auth = HTTPBasicAuth(Config.JIRA_EMAIL or "", Config.JIRA_API_TOKEN or "")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    created_tasks = []

    for req in requirements:
        # Build payload
        fields = {
            "project":     {"key": Config.JIRA_PROJECT_KEY},
            "summary":     req.get("title", "No title provided"),
            "description": format_adf_description(req.get("description", "")),
            "issuetype":   {"name": "Task"},
            "labels":      ["automated", "prd-generated"],
        }

        # Apply mapped priority if provided
        raw_prio = req.get("priority")
        if raw_prio:
            jira_prio = _PRIORITY_MAPPING.get(raw_prio, raw_prio)
            fields["priority"] = {"name": jira_prio}

        # Add optional fields if they exist in the requirement document dict
        if req.get("assignee"):
            fields["assignee"] = {"accountId": req["assignee"]}
        if req.get("estimated_hours"):
            fields["timetracking"] = {
                "originalEstimate": f"{req['estimated_hours']}h"
            }

        payload = {"fields": fields}

        # Attempt create with rate-limit retries
        max_retries = 3
        for attempt in range(max_retries + 1):
            resp = requests.post(url, json=payload, auth=auth, headers=headers)

            # Success
            if resp.status_code == 201:
                issue = resp.json()
                key = issue["key"]
                created_tasks.append({
                    "requirement_id": req.get("id"),
                    "jira_key":       key,
                    "jira_url":       f"{(Config.JIRA_URL or '').rstrip('/')}/browse/{key}"
                })
                break

            # Rate limited
            elif resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                if attempt < max_retries:
                    wait = retry_after + random.random()
                    logger.warning(f"Rate limited by Jira; retrying in {wait:.1f}s.")
                    time.sleep(wait)
                    continue
                else:
                    resp.raise_for_status()

            # Other errors
            else:
                # Attempt to parse JSON error
                err = {}
                try:
                    err = resp.json()
                except ValueError:
                    resp.raise_for_status()

                messages     = err.get("errorMessages", [])
                field_errors = err.get("errors", {})

                # If it's a priority‐field error, retry once without priority
                if "priority" in field_errors:
                    logger.warning(
                        f"Priority field rejected for requirement {req.get('id')}, "
                        "retrying without priority."
                    )
                    # Remove priority and retry immediately
                    payload["fields"].pop("priority", None)
                    resp2 = requests.post(url, json=payload, auth=auth, headers=headers)
                    if resp2.status_code == 201:
                        issue = resp2.json()
                        key = issue["key"]
                        created_tasks.append({
                            "requirement_id": req.get("id"),
                            "jira_key":       key,
                            "jira_url":       f"{(Config.JIRA_URL or '').rstrip('/')}/browse/{key}"
                        })
                        break
                    else:
                        # fail on second attempt
                        err2 = {}
                        try:
                            err2 = resp2.json()
                        except ValueError:
                            resp2.raise_for_status()
                        logger.error(
                            f"Retry without priority also failed for {req.get('id')}: "
                            f"{err2.get('errorMessages', [])} {err2.get('errors', {})}"
                        )
                        raise Exception(f"Jira API error: {err2}")
                else:
                    # other field or general error: return
                    logger.error(
                        f"Failed to create Jira issue for requirement {req.get('id')}: "
                        f"{messages} {field_errors}"
                    )
                    raise Exception(f"Jira API error: {messages} {field_errors}")

    return created_tasks
