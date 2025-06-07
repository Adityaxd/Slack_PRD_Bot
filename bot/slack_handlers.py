import json
import requests
import uuid
from slack_bolt import App
from slack_sdk.errors import SlackApiError

from bot.config import Config
from bot.analysis import analyze_document
from bot.jira_integration import create_jira_tasks

# Simple in-memory cache: maps slacks UUID → list of requirement dicts
ANALYSIS_CACHE = {}

# register checks if app is working or not : if it is working when user pings the bot, it will respond with pong
def register(app: App):
    @app.message("ping")
    def ping_pong(message, say, logger):
        say("pong")

    @app.event("message")
    def handle_message_events(event, client, say, logger):
        # only file uploads
        if event.get("subtype") != "file_share":
            return

        try:
            say("⏳ Processing your document…")
        except Exception as e:
            logger.warn(f"❌ Failed to send initial message: {e}")
            return
        
        try:
            file_meta = event["files"][0]
            file_id = file_meta["id"]
            info = client.files_info(file=file_id)["file"]
            download_url = info["url_private_download"]

            resp = requests.get(
                download_url,
                headers={"Authorization": f"Bearer {Config.SLACK_BOT_TOKEN}"}
            )
            resp.raise_for_status()
            file_bytes = resp.content

            analysis = analyze_document(file_bytes, filename=info.get("name"))
            
            # generate a short cache key
            cache_key = str(uuid.uuid4())
            # store the payload for later
            ANALYSIS_CACHE[cache_key] = [r.dict() for r in analysis.requirements]

            # build the blocks
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Found {analysis.total_requirements} requirements:*"
                    }
                }
            ]
            for req in analysis.requirements:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"• *{req.id}*: {req.title} _(Priority: {req.priority})_"
                    }
                })

            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Create Jira Tasks"},
                        "style": "primary",
                        "action_id": "create_tasks",
                        "value": cache_key
                    }
                ]
            })

            say(text="Document analysis complete! Review below:", blocks=blocks)

        except SlackApiError as e:
            logger.error(f"Slack API error: {e}")
            say("❌ Failed to fetch file. Check permissions.")
        except requests.HTTPError as e:
            logger.error(f"Download error: {e}")
            say("❌ Could not download the document.")
        except Exception as e:
            logger.error(f"Unhandled error during analysis: {e}")
            say("❌ Unexpected error processing your document.")

    @app.action("create_tasks")
    def handle_create_tasks(ack, body, client, logger):
        ack()
        try:
            cache_key = body["actions"][0]["value"]
            requirements = ANALYSIS_CACHE.pop(cache_key, None)
            if requirements is None:
                client.chat_postMessage(
                    channel=body["channel"]["id"],
                    thread_ts=body["message"]["ts"],
                    text="❌ Sorry, I no longer have that analysis cached. Please re-upload the document."
                )
                return

            created = create_jira_tasks(requirements)
            lines = [
                f"• <{item['jira_url']}|{item['jira_key']}> for {item['requirement_id']}"
                for item in created
            ]
            client.chat_postMessage(
                channel=body["channel"]["id"],
                thread_ts=body["message"]["ts"],
                text="Created the following Jira tasks:\n" + "\n".join(lines)
            )

        except Exception as e:
            logger.error(f"Jira creation failed: {e}")
            client.chat_postMessage(
                channel=body["channel"]["id"],
                thread_ts=body["message"]["ts"],
                text="❌ Failed to create Jira tasks."
            )
