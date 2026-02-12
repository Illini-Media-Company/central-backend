# # This file contains the function that reads from CHANGELOG.md and converts it from
# # markdown into HTML content that can be rendered.
# #
# # Created by Jacob Slabosz on Oct. 14, 2025
# # Last modified Oct. 14, 2025

# import os
# import re
# from markdown import markdown


# def parse_changelog():
#     """Reads from CHANGELOG.md and returns a list of dictionaries each containing the version, date and content."""
#     path = os.path.join(os.path.dirname(__file__), "..", "CHANGELOG.md")

#     if not os.path.exists(path):
#         print("Path to CHANGELOG.md does not exist. Returning empty list...")
#         return []

#     with open(path, "r", encoding="utf-8") as f:
#         changelog_md = f.read().strip()

#     # This part finds the different version headers and collects them as their own item in list
#     pattern = re.compile(
#         r"^##\s+(?:\[(.*?)\]\([^)]+\)|(.*?))\s*\((\d{4}-\d{2}-\d{2})\)", re.MULTILINE
#     )
#     matches = list(pattern.finditer(changelog_md))

#     # Loop through each match (version header)
#     releases = []  # A list of dictionaries
#     for i, match in enumerate(matches):
#         version = match.group(1) or match.group(2)
#         date = match.group(3)
#         start = match.end()
#         end = matches[i + 1].start() if i + 1 < len(matches) else len(changelog_md)
#         content_md = changelog_md[start:end].strip()

#         content_html = markdown(
#             content_md, extensions=["fenced_code", "tables", "md_in_html"]
#         )
#         releases.append(
#             {
#                 "version": version.strip(),
#                 "date": date.strip(),
#                 "content_html": content_html,
#             }
#         )

#     return releases
