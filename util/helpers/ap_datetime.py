from datetime import datetime, date, time
import calendar


# This function properly formats datetimes into AP style. It is also registered as a
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
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
            value = value.date()
        else:
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
    formatted = f"{month_str} {value.day}"

    # Add the year if it's different than the current year
    if value.year != date.today().year:
        formatted += f", {value.year}"

    return formatted


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
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
            value = value.time()
        else:
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


def days_since(date_in: date) -> int | None:
    """
    Returns the number of days since the given date.
    Args:
        `date_in` (`date`): The date to calculate from.
    Returns:
        `int`: The number of days since the date, or `None` if the input is invalid.
    """
    if not date_in:
        return None

    if isinstance(date_in, str):
        date_in = datetime.fromisoformat(date_in).date()

    if not isinstance(date_in, date):
        return None

    delta = date.today() - date_in
    return delta.days


def months_since(date_in: date) -> int | None:
    """
    Returns the number of months since the given date.
    Args:
        `date_in` (`date`): The date to calculate from.
    Returns:
        `int`: The number of months since the date, or `None` if the input is invalid.
    """
    if not date_in:
        return None

    if isinstance(date_in, str):
        date_in = datetime.fromisoformat(date_in).date()

    if not isinstance(date_in, date):
        return None

    today = date.today()
    months = (today.year - date_in.year) * 12 + (today.month - date_in.month)

    if today.day < date_in.day:
        months -= 1

    return months


def years_since(date_in: date) -> int | None:
    """
    Returns the number of years since the given date.
    Args:
        `date_in` (`date`): The date to calculate from.
    Returns:
        `int`: The number of years since the date, or `None` if the input is invalid.
    """
    if not date_in:
        return None

    if isinstance(date_in, str):
        date_in = datetime.fromisoformat(date_in).date()

    if not isinstance(date_in, date):
        return None

    today = date.today()
    years = today.year - date_in.year

    if (today.month, today.day) < (date_in.month, date_in.day):
        years -= 1

    return years


def time_since(date_in: date) -> str | None:
    if not date_in:
        return None

    if isinstance(date_in, str):
        date_in = datetime.fromisoformat(date_in).date()

    if not isinstance(date_in, date):
        return None

    today = date.today()

    # Calculate years
    years = today.year - date_in.year
    if (today.month, today.day) < (date_in.month, date_in.day):
        years -= 1

    # Calculate months
    if today.month >= date_in.month:
        months = today.month - date_in.month
    else:
        months = 12 + (today.month - date_in.month)

    if today.day < date_in.day:
        months -= 1
        # If subtracting a month makes it negative, wrap around to 11
        if months < 0:
            months = 11

    last_month_anniversary_year = (
        today.year if today.month > 1 or months < 11 else today.year - 1
    )

    temp_date = date_in
    # Advance temp_date by years and months
    new_month = (date_in.month + months - 1) % 12 + 1
    new_year = date_in.year + years + (date_in.month + months - 1) // 12

    # Handle end-of-month edge cases (e.g., Jan 31 -> Feb 28)
    try:
        anniversary_date = date(new_year, new_month, date_in.day)
    except ValueError:
        _, last_day = calendar.monthrange(new_year, new_month)
        anniversary_date = date(new_year, new_month, last_day)

    days = (today - anniversary_date).days

    return f"{years}y, {months}m, {days}d"
