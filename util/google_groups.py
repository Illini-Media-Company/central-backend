"""
This file contains utility functions for managing Google Group memberships. All functions
are executed with admin credentials. 

Created by Jacob Slabosz on Feb. 2, 2026
Last modified Feb. 3, 2026
"""

from googleapiclient.discovery import build
from util.security import get_admin_creds

MEMBER_SCOPE = ["https://www.googleapis.com/auth/admin.directory.group.member"]
GROUP_SCOPE = ["https://www.googleapis.com/auth/admin.directory.group"]


def manage_group_membership(
    group_email: str, user_email: str, action: str = "add"
) -> tuple[bool, str | None]:
    """
    Uses admin credentials to add or remove a user from a Google Group.

    Arguments:
        `group_email` (`str`): The email of the Google Group
        `user_email` (`str`): The email of the user to be added or removed
        `action` (`str`): Either "add" or "remove"

    Returns:
        tuple (`bool`, `str`): Whether the operation was successful and an error message if not

    """

    creds = get_admin_creds(MEMBER_SCOPE)

    with build("admin", "directory_v1", credentials=creds) as service:
        try:
            if action == "add":
                member = {"email": user_email, "role": "MEMBER"}
                service.members().insert(groupKey=group_email, body=member).execute()
                print(f"Successfully added {user_email} to {group_email}")

            elif action == "remove":
                service.members().delete(
                    groupKey=group_email, memberKey=user_email
                ).execute()
                print(f"Successfully removed {user_email} from {group_email}")

        except Exception as e:
            error_msg = str(e).lower()

            # User in group when trying to add (409 Conflict)
            if action == "add" and "alreadyexists" in error_msg.replace(" ", ""):
                print(f"User {user_email} is already in {group_email}. Skipping.")
                return True, None

            # User not in group when trying to remove (404 Not Found)
            if action == "remove" and "memberkey" in error_msg:
                print(
                    f"User {user_email} not found in {group_email}. Skipping removal."
                )
                return True, None

            # All other errors
            print(f"Google Directory API Error: {e}")
            return False, str(e)

    return True, None


def update_group_membership(
    user_email: str, old_groups: list[str], new_groups: list[str]
) -> tuple[bool, str | None]:
    """
    Updates a user's Google Group memberships based on the groups the user was previously in
        and the groups they should now be in. Ignores all groups that are not included in either list.

    Arguments:
        `user_email` (`str`): The email of the user to update
        `old_groups` (`list[str]`): List of emails for the groups the user is/was in
        `new_groups` (`list[str]`): List of emails for the groups the user should be in

    Returns:
        tuple (`bool`, `str | None`): Whether the operation was successful and an error message if not
    """
    print(f"Updating groups for {user_email}")
    print(f"Old groups: {old_groups}")
    print(f"New groups: {new_groups}")

    remove_from_groups = list(set(old_groups) - set(new_groups))
    add_to_groups = list(set(new_groups) - set(old_groups))
    print(remove_from_groups)
    print(add_to_groups)

    if remove_from_groups:
        print("Removing from groups:")
        for group in remove_from_groups:
            # Remove user from group
            print(f" - {group}")
            success, error = manage_group_membership(group, user_email, action="remove")
            if not success:
                print(f"\tError removing user from group {group}: {error}")
                return False, error
            else:
                print("\tDone.")
    if add_to_groups:
        print("Adding to groups:")
        for group in add_to_groups:
            # Add user to group
            print(f" - {group}")
            success, error = manage_group_membership(group, user_email, action="add")
            if not success:
                print(f"\tError adding user to group {group}: {error}")
                return False, error
            else:
                print("\tDone.")

    return True, None


def check_group_exists(group_email: str) -> bool:
    """
    Checks if a Google Group exists.

    Arguments:
        `group_email` (`str`): The email of the Google Group
    Returns:
        `bool`: Whether the group exists
    """
    creds = get_admin_creds(GROUP_SCOPE)

    with build("admin", "directory_v1", credentials=creds) as service:
        try:
            service.groups().get(groupKey=group_email).execute()
            return True
        except Exception as e:
            # Check if it was not found or some other error
            if "notfound" in str(e).lower().replace(" ", ""):
                return False

            # If it's a different error (like a 403 Permission error),
            # you might want to log it or raise it.
            print(f"Error checking group existence: {e}")
            return False
