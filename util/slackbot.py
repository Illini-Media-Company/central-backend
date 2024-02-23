from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import signal
import os

print("\n\n\n")

imcGeneralID = "C06GADGT60Z"
diAnnouncementsID = "C06G089F8S0"
illioAnnouncementsID = "C06FXMB42MR"
wpguAnnouncementsID = "C06G08KP11S"
cwaGeneralID = "C06FXQSRB5G"

imcAdvertisingID = "C06FR635SPQ"
imcMarketingID = "C06FR63HURL"
imcFrontDeskButton = "C06FUT4LHHT"

illioDesignID = "C06FXMHUQ3V"
illioPhotoID = "C06GAE3QKMX"
illioWriterID = "C06FH8HF46B"

wpguEngineeringID = "C06G08SQZEG"
wpguIlliniDriveID = "C06FXMKG97D"
wpguMarketingID = "C06FXMKPMU3"
wpguMusicID = "C06GLJD5VUY"
wpguNewsID = "C06FXML7BHR"
wpguOnAirID = "C06FR61KDJS"
wpguProductionID = "C06FXQXKJAE"

        
illioMessage = [
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "*Choose your section(s) within Illio Yearbook:*"
    }
  },
  {
    "type": "actions",
    "elements": [
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": ":computer: Designer",
          "emoji": True
        },
        "value": "click_me_123",
        "action_id": "illioDesignButton"
      },
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": ":camera_with_flash: Photographer",
          "emoji": True
        },
        "value": "click_me_123",
        "action_id": "illioPhotoButton"
      },
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": ":pencil: Writer",
          "emoji": True
        },
        "value": "click_me_123",
        "action_id": "illioWriterButton"
      }
    ]
}]

illioMessageText = "Choose your section(s) within Illio Yearbook"

wpguMessage = [{
  "type": "section",
  "text": {
    "type": "mrkdwn",
    "text": "*Choose your section(s) within WPGU 107.1 FM:*"
  }
},
{
  "type": "actions",
  "elements": [
    {
      "type": "button",
      "text": {
        "type": "plain_text",
        "text": ":gear: Engineering",
        "emoji": True
      },
      "value": "click_me_123",
      "action_id": "wpguEngineeringButton"
    },
    {
      "type": "button",
      "text": {
        "type": "plain_text",
        "text": ":basketball: Illini Drive",
        "emoji": True
      },
      "value": "click_me_123",
      "action_id": "wpguIlliniDriveButton"
    },
    {
      "type": "button",
      "text": {
        "type": "plain_text",
        "text": ":desktop_computer: Marketing",
        "emoji": True
      },
      "value": "click_me_123",
      "action_id": "wpguMarketingButton"
    },
    {
      "type": "button",
      "text": {
        "type": "plain_text",
        "text": ":musical_note: Music",
        "emoji": True
      },
      "value": "click_me_123",
      "action_id": "wpguMusicButton"
    },
    {
      "type": "button",
      "text": {
        "type": "plain_text",
        "text": ":newspaper: News",
        "emoji": True
      },
      "value": "click_me_123",
      "action_id": "wpguNewsButton"
    },
    {
      "type": "button",
      "text": {
        "type": "plain_text",
        "text": ":studio_microphone: On-Air",
        "emoji": True
      },
      "value": "click_me_123",
      "action_id": "wpguOnAirButton"
    },
    {
      "type": "button",
      "text": {
        "type": "plain_text",
        "text": ":level_slider: Production",
        "emoji": True
      },
      "value": "click_me_123",
      "action_id": "wpguProductionButton"
    }
  ]
}]

wpguMessageText = "Choose your section(s) within WPGU 107.1 FM"

imcMessage = [
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "*Choose your department within IMC Business:*"
    }
  },
  {
    "type": "actions",
    "elements": [
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": ":newspaper: Advertising",
          "emoji": True
        },
        "value": "click_me_123",
        "action_id": "imcAdvertisingButton"
      },
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": ":desktop_computer: Marketing",
          "emoji": True
        },
        "value": "click_me_123",
        "action_id": "imcMarketingButton"
      },
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": ":pushpin: Front Desk",
          "emoji": True
        },
        "value": "click_me_123",
        "action_id": "imcFrontDeskButton"
      }
    ]
}]

imcMessageText = "Choose your section within IMC Business"

imcWelcomeMessage = [
  {
    "type": "header",
    "text": {
      "type": "plain_text",
      "text": ":imc: Welcome to Illini Media Company! :imc:",
      "emoji": True
    }
  },
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "This Slack workspace serves as the communication hub for all things related to Illini Media Company. Here, you’ll be able to communicate with all your peers, both within your department and in other departments."
    }
  },
  {
    "type": "divider"
  },
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": ":bell:\nMake sure you have downloaded Slack on both your phone and laptop and have all notifications turned on. You'll have to click \"You\" in the bottom right corner, then \"Notifications,\" then change the top option to \"All new messages.\""
    }
  },
  {
    "type": "divider"
  },
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": ":adult:\nStart by customizing your profile! All users should have their full name in their Slack profile, along with a profile photo (it doesn't have to be you). You should also add your title. You should format your title as follows:\n\n\"[Department] — [Title]\"\n\nFor example, a staff photography for The Daily Illini would input \"DI — Staff Photographer\"\n\nFor those with positions in multiple departments, format it as follows:\n\n\"DI — Staff Photographer | Illio — Staff Photographer\""
    }
  },
  {
    "type": "divider"
  },
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": ":Calendar:\nMake sure you’ve connected Google Calendar to Slack! This allows all of your meetings to seamlessly integrate with Slack. In your list of channels, you should see the Google Calendar app at the bottom. Click that and make sure you log in!"
    }
  },
  {
    "type": "divider"
  },
  {
    "type": "section",
    "text": {
      "type": "plain_text",
      "text": "To begin, use the buttons below to choose your IMC department. If you are in multiple, you can click multiple buttons.",
      "emoji": True
    }
  },
  {
    "type": "actions",
    "elements": [
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": ":dailyillini: The Daily Illini :dailyillini:",
          "emoji": True
        },
        "value": "click_me_123",
        "action_id": "daily_illini_button"
      },
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": ":illio: Illio Yearbook :illio:",
          "emoji": True
        },
        "value": "click_me_123",
        "action_id": "illio_button"
      },
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": ":wpgu: WPGU 107.1 FM :wpgu:",
          "emoji": True
        },
        "value": "click_me_123",
        "action_id": "wpgu_button"
      },
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": ":cwa: Creative Works Agency :cwa:",
          "emoji": True
        },
        "value": "click_me_123",
        "action_id": "cwa_button"
      },
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": ":imc: IMC Business :imc:",
          "emoji": True
        },
        "value": "click_me_123",
        "action_id": "imc_business_button"
      }
    ]
  }
]

imcWelcomeMessageText = "Welcome to Illini Media Company!"


app = App(
   token= os.environ.get("SLACK_BOT_TOKEN"),
   signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),

)

@app.event("app_mention")
def handle_mention(event, say):
    channel:"C06GADGT60Z"
    say("IMC Welcome Bot is up and running")

def bot_status():
    app.client.chat_postMessage(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        channel="C06GADGT60Z",
        text="IMC Welcome Bot is running"
    )

bot_status()

#app.scheduler.schedule(interval=1000*30* 60, func=bot_status)
@app.event("member_joined_channel")
def member_joined_channel(event):
    user_id = event['user']
    channel_id = event['channel']
    print("\nUser " + user_id+ " joined channel " + channel_id)
    print(channel_id + " Here")
    if channel_id == imcGeneralID:
        directMessage = user_id
        print("   User ID: " + user_id)
        app.client.chat_postMessage( 
            token=os.environ.get("SLACK_BOT_TOKEN"),
            channel=directMessage,
            blocks=imcWelcomeMessage,
            text=imcWelcomeMessageText
        )
        print("   Message sent.\n")
    elif channel_id == illioAnnouncementsID:
        directMessage = user_id
        print("   User ID: " + user_id)
        app.client.chat_postMessage( 
            token=os.environ.get("SLACK_BOT_TOKEN"),
            channel=directMessage,
            blocks=illioMessage,
            text=illioMessageText
        )
        print("   Message sent.\n")
    elif channel_id == wpguAnnouncementsID:
        directMessage = user_id
        print("   User ID: " + user_id)
        app.client.chat_postMessage( 
            token=os.environ.get("SLACK_BOT_TOKEN"),
            channel=directMessage,
            blocks=wpguMessage,
            text=wpguMessageText
        )
        print("   Message sent.\n")
    else:
        print("  Not a channel of interest. No messages sent.")

def buttonWrapper(buttonName, buttonHashtag, channel, userName, userId):
    print("User " + userName +" clicked "+ buttonName +" Button")

    try:
        app.client.conversations_invite(
            token=os.environ.get("SLACK_BOT_TOKEN"),
            channel=channel,
            users=userId,
            force=True
        )
        app.client.chat_postMessage(
            token=os.environ.get("SLACK_BOT_TOKEN"),
            channel=userId,
            text=userName + ", you have been added to "+ buttonHashtag
        )
        print("  User " + userName + " has been added to "+ buttonHashtag +"\n")
    except Exception as e:
        app.client.chat_postMessage(
            token=os.environ.get("SLACK_BOT_TOKEN"),
            channel=userId,
            text=userName + ", you are already in "+ buttonHashtag
        )
        print("Users "+ userName+" is already in "+ buttonHashtag+"\n")

#Executed if a user clicks the "The Daily Illini" button
@app.action("daily_illini_button")
def dailyIlliniButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("Daily Illini", "#di_announcements", diAnnouncementsID, userName, userId)

#Executed if a user clicks the "WPGU 107.1 FM" button
@app.action("wpgu_button")
def wpguButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("WPGU", "#wpgu_announcements", wpguAnnouncementsID, userName, userId)

#Executed if a user clicks the "Illio Yearbook" button
@app.action("illio_button")
def illioButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("Illio", "#illio_announcements", illioAnnouncementsID, userName, userId)

#Executed if a user clicks the "Creative Works Agency" button
@app.action("cwa_button")
def cwaButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("Creative Works Agency", "#cwa_general", cwaGeneralID, userName, userId)

#Executed if a user clicks the "IMC Business" button
@app.action('imc_business_button')   
def imcBusinessButton(ack,body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    print("User " + userName +" clicked IMC Business button")

    #direct message the user
    app.client.chat_postMessage(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        channel=userId,

        blocks= imcMessage,
        text=imcMessageText
    )

    print("    Section choose message sent.\n")

#ILLIO BUTTONS
    
#Executed if a user clicks the Illio Design button  
@app.action("illioDesignButton")
def illioDesignButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("Illio Design", "#illio_design", illioDesignID, userName, userId)

#Executed if a user clicks the Illio Photo button
@app.action("illioPhotoButton")
def illioPhotoButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("Illio Photo", "#illio_photo", illioPhotoID, userName, userId)

#Executed if a user clicks the Illio Writer button
@app.action("illioWriterButton")
def illioWriterButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("Illio Writer", "#illio_writer", illioWriterID, userName, userId)

#WPGU BUTTONS
        
#Executed if a user clicks the WPGU Engineering button
@app.action("wpguEngineeringButton")
def wpguEngineeringButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("WPGU Engineering", "#wpgu_engineering", wpguEngineeringID, userName, userId)

#Executed if a user clicks the WPGU IlliniDriveButton
@app.action("wpguIlliniDriveButton")
def wpguIlliniDriveButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("WPGU Illini Drive", "#wpgu_illinidrive", wpguIlliniDriveID, userName, userId)

#Executed if a user clicks the WPGU Marketing button
@app.action("wpguMarketingButton")
def wpguMarketingButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("WPGU Marketing", "#wpgu_marketing", wpguMarketingID, userName, userId)
  
#Executed if a user clicks on the WPGU Music button
@app.action("wpguMusicButton")
def wpguMusicButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("WPGU Music", "#wpgu_music", wpguMusicID, userName, userId)

#executed if a user clicks the WPGU News Button
@app.action("wpguNewsButton")
def wpguNewsButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("WPGU News", "#wpgu_news", wpguNewsID, userName, userId)

#Executed if a user clicks the WPGU On-Air button
@app.action("wpguOnAirButton")
def wpguOnAirButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("WPGU On-Air", "#wpgu_on-air", wpguOnAirID, userName, userId)

#Executed if a user clicks the WPGU Production button
@app.action("wpguProductionButton")
def wpguProductionButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("WPGU Production", "#wpgu_production", wpguProductionID, userName, userId)

#IMC Business Button
        
#Executed if a user clicks the IMC Advertising button
@app.action("imcAdvertisingButton")
def imcAdvertisingButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("IMC Advertising", "#imc_advertising", imcAdvertisingID, userName, userId)

#Executed if a user clicks the IMC Marketing button
@app.action("imcMarketingButton")
def imcMarketingButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("IMC Marketing", "#imc_marketing", imcMarketingID, userName, userId)

#executed if a user clicks the IMC Front Desk button
@app.action("imcFrontDeskButton")
def imcFrontDeskButton(ack, body, logger):
    ack()
    logger.info(body)
    userName = body["user"]["name"]
    userId = body["user"]["id"]
    buttonWrapper("IMC Front Desk", "#imc_frontdesk", imcFrontDeskButton, userName, userId)

def handle_sigint():
    print("Stopping IMC Welcome Bot...")
    app.client.chat_postMessage(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        channel=imcGeneralID,
        text= "IMC Welcome Bot stopped"
    )
    exit()

signal.signal(signal.SIGINT, handle_sigint)

if __name__ == "__main__":
    SocketModeHandler(app,os.environ["SLACK_APP_TOKEN"]).start()

