from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from bot.config import Config
import bot.slack_handlers  as handlers

import logging

logging.basicConfig(level=logging.DEBUG)

def main():
    # Check all config values are set
    Config.validate()

    # Initialize the Slack app
    app = App(
        token=Config.SLACK_BOT_TOKEN,
        signing_secret=Config.SLACK_SIGNING_SECRET
    )

    # Register all Slack handlers
    handlers.register(app)

    # Start the Socket listener
    handler = SocketModeHandler(app, Config.SLACK_APP_TOKEN)
    handler.start()

if __name__ == "__main__":
    main()
