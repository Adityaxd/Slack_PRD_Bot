import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Slack 
    SLACK_BOT_TOKEN      = os.getenv("SLACK_BOT_TOKEN")
    SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
    SLACK_APP_TOKEN      = os.getenv("SLACK_APP_TOKEN")

    # Jira 
    JIRA_URL            = os.getenv("JIRA_URL")
    JIRA_EMAIL          = os.getenv("JIRA_EMAIL")
    JIRA_API_TOKEN      = os.getenv("JIRA_API_TOKEN")
    JIRA_PROJECT_KEY    = os.getenv("JIRA_PROJECT_KEY")  # e.g., 'PROJ'

    # LLM
    OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY")
    ANALYSIS_MODEL      = os.getenv("ANALYSIS_MODEL", "openai")  # 'openai', 'claude', or 'local'

    @classmethod
    def validate(cls):
        missing = []
        for var in [
            "SLACK_BOT_TOKEN",
            "SLACK_SIGNING_SECRET",
            "SLACK_APP_TOKEN",
            "JIRA_URL",
            "JIRA_EMAIL",
            "JIRA_API_TOKEN",
            "JIRA_PROJECT_KEY",
            "OPENAI_API_KEY"
        ]:
            if not getattr(cls, var):
                missing.append(var)
        if missing:
            raise RuntimeError(f"Missing required config vars: {', '.join(missing)}")
        if cls.ANALYSIS_MODEL not in ["openai", "claude", "local"]:
            raise ValueError(f"Invalid ANALYSIS_MODEL: {cls.ANALYSIS_MODEL}. Must be one of 'openai', 'claude', or 'local'.")