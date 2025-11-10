from datetime import datetime, date, time


# This function properly formates datetimes into AP style. It is also registered as a
# Jinja filter to it can be used in HTML templates by appending |ap_datetime to a variable.
def ap_datetime(value):
    """Format a datetime in AP style using ap_date and ap_time. Returns -1 if the input is incorrect."""
    if not value:
        return ""

    if isinstance(value, str):
        value = datetime.fromisoformat(value)

    date = ap_date(value)
    time = ap_time(value)

    if date == -1 or time == -1:
        return -1

    return f"{date}, {time}"


def ap_daydatetime(value):
    """Format a datetime in AP style using ap_date and ap_time, including the dat of the week. Returns -1 if the input is incorrect."""
    if not value:
        return ""

    if isinstance(value, str):
        value = datetime.fromisoformat(value)

    date_time = ap_datetime(value)
    if date_time == -1:
        return -1

    return f"{value.strftime('%A')}, {date_time}"


def ap_date(value):
    """Format a date in AP style (month abbreviations, day). Returns -1 if the input is incorrect."""
    if not value:
        return ""

    # Extract the date if this is a datetime
    if isinstance(value, datetime):
        value = value.date()

    # Return -1 if the input is incorrect
    if not isinstance(value, date):
        return -1

    # Abbreviate the months to be consistent with AP style
    ap_months = {
        "January": "Jan.",
        "February": "Feb.",
        "August": "Aug.",
        "September": "Sept.",
        "October": "Oct.",
        "November": "Nov.",
        "December": "Dec.",
    }

    month_str = ap_months.get(value.strftime("%B"), value.strftime("%B"))
    return f"{month_str} {value.day}"


def ap_daydate(value):
    """Format a date in AP style (month abbreviations, day) including the day of the week. Returns -1 if the input is incorrect."""
    if not value:
        return ""

    if isinstance(value, str):
        value = datetime.fromisoformat(value)

    date_str = ap_date(value)
    if date_str == -1:
        return -1

    return f"{value.strftime('%A')}, {date_str}"


def ap_time(value):
    """Format a time in AP style (12-hour with a.m./p.m.). Returns -1 if the input is incorrect."""
    if not value:
        return ""

    # Extract the time if this is a datetime
    if isinstance(value, datetime):
        value = value.time()

    # Return -1 if the input is incorrect
    if not isinstance(value, time):
        return -1

    hour = value.strftime("%I").lstrip("0")  # 12-hour format without leading zero
    minute = value.minute

    # Properly format a.m. and p.m.
    ampm = value.strftime("%p").lower().replace("am", "a.m.").replace("pm", "p.m.")

    if value.hour == 0 and value.minute == 0:
        # Use midnight instead of 12 a.m.
        return "midnight"
    elif value.hour == 12 and value.minute == 0:
        # Use noon instead of 12 p.m.
        return "noon"
    elif minute == 0:
        # Remove trailing zeroes from hour if no minute
        return f"{hour} {ampm}"
    else:
        return f"{hour}:{value.strftime('%M')} {ampm}"
