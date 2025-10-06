from flask import Blueprint, redirect, request, url_for
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bolt.adapter.socket_mode import SocketModeHandler
from util.slackbot import app
from flask_login import login_required

from constants import ENV, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET
from util.security import csrf

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types
import requests
import sys


@app.command("/start_gemini_news_bot")
def repeat_text(ack, say, command):
    # Acknowledge command request
    ack()
    response = get_gemini_response(command["text"])
    say(response)


def get_news_gazette():
    """
    This is where the News Gazette scraper will be called.
    """
    # request and parse NG's home page
    page = requests.get("https://www.news-gazette.com/")
    soup = BeautifulSoup(page.content, "html.parser")

    # scrape all links on the page, then filter for relevant URLs
    all_links = soup.find_all("a", class_="tnt-asset-link")
    filtered_links = []
    for link in all_links:
        url_tags = ["/news", "/business", "/arts-entertainment", "/sports"]
        for url_tag in url_tags:
            if link.get("href").startswith(url_tag) and "photo" not in link.get("href"):
                filtered_links.append(link.get("href"))
                break

    # loop through all links and build our data
    data = []
    for i in range(len(filtered_links)):
        article = requests.get(f"https://www.news-gazette.com{filtered_links[i]}")
        article_soup = BeautifulSoup(article.content, "html.parser")
        title = article_soup.find("title").text.split(" |")[0]
        date_posted = article_soup.find(class_="tnt-date").get("datetime")
        url = f"https://www.news-gazette.com{filtered_links[0]}"

        # getting article content is a bit more complicated, as it's not in a single HTML element
        paragraphs = article_soup.find_all("p")
        content = ""
        for paragraph in paragraphs:
            content += paragraph.text

        data.append(
            {
                "title": title,
                "content": content,
                "date_posted": date_posted,
                "url_to_source": url,
            }
        )
    return data


def get_gemini_response(prompt: str) -> str:
    client = genai.Client()
    tools = [get_news_gazette]

    response = client.models.generate_content(
        model="gemini-2.0-flash-001",
        contents=f"""{prompt} When answering this query, use sources
                     from Reddit and News Gazette.""",
        config=types.GenerateContentConfig(
            tools=tools,
        ),
    )

    return response.text
