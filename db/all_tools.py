# This file defines the Tool and ToolCategory classes that hold information about the tools that are displayed
# on the homepage of the Illini Media Console.
# All functions MUST by called within "with client.context():"
#
# Created by Jacob Slabosz on Oct. 1, 2025
# Last modified Oct. 1, 2025

from google.cloud import ndb
from datetime import datetime
from zoneinfo import ZoneInfo
from flask_login import current_user
from util.security import is_user_in_group


class Tool(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    updated_datetime = ndb.DateTimeProperty()  # When the tool was last updated
    name = ndb.StringProperty()  # The name of the tool
    description = (
        ndb.StringProperty()
    )  # A short description of the tool (1-2 sentences)
    icon = (
        ndb.StringProperty()
    )  # The Bootstrap Icon class for the tool (e.g. "bi bi-database-fill-gear")
    url = (
        ndb.StringProperty()
    )  # The URL the tool links to. If external, should be the full url. If internal, should only be the path
    category = ndb.StringProperty()  # The name of the category th tool belongs to
    restricted_to = ndb.StringProperty(
        repeated=True
    )  # A list of the Google Groups that this is restricted to


class ToolCategory(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    name = ndb.StringProperty()  # The name of the category
    create_datetime = ndb.DateTimeProperty()  # When the category was created


# Need to call this function with client.context():
def create_tool(name, description, icon, url, category, restricted_to):
    """Creates a new tool in the database."""

    print(f"Creating new tool...")

    # Check if the category exists
    category_query = ToolCategory.query(ToolCategory.name == category).get()
    if not category_query:
        # If the category doesn't exist, create it (this is the only way categories are created)
        new_category = ToolCategory(
            name=category,
            create_datetime=datetime.now(ZoneInfo("America/Chicago")).replace(
                tzinfo=None
            ),
        )
        new_category.put()

    # Create the tool
    tool = Tool(
        name=name,
        description=description,
        icon=icon,
        url=url,
        category=category,
        restricted_to=restricted_to if restricted_to is not None else [],
        updated_datetime=datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None),
    )
    tool.put()

    print(f"Created tool '{name}' with ID {tool.uid}\n")

    return tool


# Modifies an existing tool. Tool must be specified by ID. All others are optional
def modify_tool(uid, name, description, icon, url, category, restricted_to):
    """Modifies an existing tool"""

    print(f"Modifying tool with ID {uid}...")

    tool = Tool.get_by_id(uid)

    if tool:
        tool.name = name if name is not None else tool.name
        tool.description = description if description is not None else tool.description
        tool.icon = icon if icon is not None else tool.icon
        tool.url = url if url is not None else tool.url
        tool.category = category if category is not None else tool.category
        tool.restricted_to = (
            restricted_to if restricted_to is not None else tool.restricted_to
        )
        tool.updated_datetime = datetime.now(ZoneInfo("America/Chicago")).replace(
            tzinfo=None
        )

        tool.put()
        print(f"Modified tool with ID {uid}.\n")
        return tool
    else:
        print(f"Tool not found.\n")
        return None


def remove_tool(uid):
    print(f"Removing tool with ID {uid}...")
    tool = Tool.get_by_id(uid)

    if tool is not None:
        tool.key.delete()
        print("\tTool removed.")
        return True
    else:
        print("\tTool not found.")
        return False


def remove_category(category_name):
    print(f"Removing category '{category_name}'...")
    category = ToolCategory.query(ToolCategory.name == category_name).get()

    if category:
        if get_tools_by_category(category_name):
            print("\tCategory not empty. Did not remove.")
            return "NOTEMPTY"
        else:
            category.key.delete()
            print("\tCategory removed.")
            return True
    else:
        print("\tCategory not found.")
        return False


def get_categories():
    """Return a list of the names of all categories, sorted alphabetically"""

    return [
        category.name
        for category in ToolCategory.query().order(ToolCategory.name).fetch()
    ]


def get_tools_by_category(category_name):
    """Return a list of dicts of the tools that fall under a specified category, sorted alphabetically"""

    return [
        tool.to_dict()
        for tool in Tool.query(Tool.category == category_name).order(Tool.name).fetch()
    ]


def get_tools_by_category_restricted(category_name):
    """Return a list of dicts of the tools that fall under a specified category, sorted alphabetically.
    Only returns tools that are accessible by the current user. This function MUST be called within
    a Flask request context, otherwise it will fail due to current_user being accessed outside of scope
    """

    return [
        tool.to_dict()
        for tool in Tool.query(Tool.category == category_name).order(Tool.name).fetch()
        if not tool.restricted_to or is_user_in_group(current_user, tool.restricted_to)
    ]


def get_all_tools():
    """Returns a dict mapping category names to a list of tool dicts.
    Returns all tools regardless of user's groups"""

    category_names = get_categories()
    result = {}

    for category in category_names:
        tools = get_tools_by_category(category)
        result[category] = tools

    return result


def get_all_tools_restricted():
    """Returns a dict mapping category names to a list of tool dicts.
    Only returns tools that are accessible by groups that the user is in.
    This function MUST be called within a Flask request context, otherwise
    it will fail due to current_user being accessed outside of scope"""

    category_names = get_categories()
    result = {}

    for category in category_names:
        tools = get_tools_by_category_restricted(category)
        if tools:
            result[category] = tools

    return result
