"""
Timezone utilities for handling Indian Standard Time (IST) conversion.

Industry Best Practice: Store in UTC, Display in Local Time
============================================================

This follows the Fortune 500 standard approach:
1. Database: Always store in UTC (timezone-aware datetime)
2. Business Logic: Use IST timezone for calculations (schedules, working hours, etc.)
3. API Display: Convert to IST for Indian users
4. Frontend: Send timezone info so frontend can localize further if needed

Reference: Google, Amazon, Microsoft, Stripe all follow this pattern

Example Usage:
--------------
# In models.py - Storage (automatic with USE_TZ=True)
class Event(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)  # Stores in UTC

# In business logic - Calculations
from utils.timezone_utils import get_current_time_ist, is_within_school_hours

current_time_ist = get_current_time_ist()
if is_within_school_hours(current_time_ist):
    # Business logic here
    pass

# In serializers - Display
from utils.timezone_utils import to_ist

class EventSerializer(serializers.ModelSerializer):
    timestamp_ist = serializers.SerializerMethodField()

    def get_timestamp_ist(self, obj):
        return to_ist(obj.timestamp)

# In views - Query filtering
from utils.timezone_utils import get_start_of_day_ist, get_end_of_day_ist

today_start = get_start_of_day_ist()
today_end = get_end_of_day_ist()
events_today = Event.objects.filter(timestamp__range=[today_start, today_end])
"""

from datetime import datetime, time

from django.utils import timezone
import pytz

# Indian Standard Time timezone
IST = pytz.timezone("Asia/Kolkata")


def to_ist(dt: datetime) -> datetime:
    """
    Convert a timezone-aware datetime to Indian Standard Time.

    Args:
        dt: Timezone-aware datetime (typically in UTC from database)

    Returns:
        Datetime converted to IST timezone

    Example:
        >>> utc_time = timezone.now()  # 2024-01-15 10:00:00 UTC
        >>> ist_time = to_ist(utc_time)  # 2024-01-15 15:30:00 IST
    """
    if dt is None:
        return None

    if timezone.is_naive(dt):
        # If naive, assume it's UTC (database default)
        dt = timezone.make_aware(dt, pytz.utc)

    return dt.astimezone(IST)


def to_utc(dt: datetime) -> datetime:
    """
    Convert a datetime to UTC (for storage).

    Args:
        dt: Datetime in any timezone (or naive, assumed IST)

    Returns:
        Datetime converted to UTC timezone

    Example:
        >>> ist_time = datetime(2024, 1, 15, 15, 30)  # Naive IST
        >>> utc_time = to_utc(ist_time)  # 2024-01-15 10:00:00 UTC
    """
    if dt is None:
        return None

    if timezone.is_naive(dt):
        # Assume naive datetime is in IST
        dt = IST.localize(dt)

    return dt.astimezone(pytz.utc)


def get_current_time_ist() -> datetime:
    """
    Get current time in Indian Standard Time.

    Returns:
        Current datetime in IST timezone

    Example:
        >>> now_ist = get_current_time_ist()
        >>> print(now_ist.tzinfo)  # Asia/Kolkata
    """
    return timezone.now().astimezone(IST)


def get_start_of_day_ist(date: datetime | None = None) -> datetime:
    """
    Get start of day (00:00:00) in IST, returned in UTC for database queries.

    Args:
        date: Date to get start of (defaults to today)

    Returns:
        Start of day in UTC (for database filtering)

    Example:
        >>> today_start = get_start_of_day_ist()
        >>> events = Event.objects.filter(timestamp__gte=today_start)
    """
    if date is None:
        date = get_current_time_ist()
    else:
        date = to_ist(date)

    # Get start of day in IST
    start_of_day_ist = IST.localize(datetime.combine(date.date(), time.min))

    # Convert to UTC for database query
    return start_of_day_ist.astimezone(pytz.utc)


def get_end_of_day_ist(date: datetime | None = None) -> datetime:
    """
    Get end of day (23:59:59.999999) in IST, returned in UTC for database queries.

    Args:
        date: Date to get end of (defaults to today)

    Returns:
        End of day in UTC (for database filtering)

    Example:
        >>> today_end = get_end_of_day_ist()
        >>> events = Event.objects.filter(timestamp__lte=today_end)
    """
    if date is None:
        date = get_current_time_ist()
    else:
        date = to_ist(date)

    # Get end of day in IST
    end_of_day_ist = IST.localize(datetime.combine(date.date(), time.max))

    # Convert to UTC for database query
    return end_of_day_ist.astimezone(pytz.utc)


def is_within_school_hours(dt: datetime | None = None, start_hour: int = 6, end_hour: int = 20) -> bool:
    """
    Check if given time is within school operating hours (in IST).

    Args:
        dt: Datetime to check (defaults to now)
        start_hour: School start hour in 24h format (default: 6 AM)
        end_hour: School end hour in 24h format (default: 8 PM)

    Returns:
        True if within school hours

    Example:
        >>> if is_within_school_hours():
        >>>     # Send notification
        >>>     pass
    """
    if dt is None:
        dt = get_current_time_ist()
    else:
        dt = to_ist(dt)

    current_hour = dt.hour
    return start_hour <= current_hour < end_hour


def format_datetime_ist(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    """
    Format datetime in IST with timezone info.

    Args:
        dt: Datetime to format
        format_str: Python datetime format string

    Returns:
        Formatted datetime string in IST

    Example:
        >>> event_time = Event.objects.first().timestamp
        >>> formatted = format_datetime_ist(event_time)
        >>> # "2024-01-15 15:30:00 IST"
    """
    if dt is None:
        return None

    ist_time = to_ist(dt)
    return ist_time.strftime(format_str)


def get_time_range_today_ist() -> tuple[datetime, datetime]:
    """
    Get today's time range in UTC for database queries.

    Returns:
        Tuple of (start_of_today_utc, end_of_today_utc)

    Example:
        >>> start, end = get_time_range_today_ist()
        >>> today_events = Event.objects.filter(
        >>>     timestamp__gte=start,
        >>>     timestamp__lte=end
        >>> )
    """
    return get_start_of_day_ist(), get_end_of_day_ist()


def ist_time_to_utc_time(hour: int, minute: int = 0) -> time:
    """
    Convert IST time (hour:minute) to UTC time.
    Useful for schedule comparisons.

    Args:
        hour: Hour in IST (0-23)
        minute: Minute (0-59)

    Returns:
        time object in UTC

    Example:
        >>> # School starts at 7:30 AM IST
        >>> utc_start = ist_time_to_utc_time(7, 30)
        >>> # Now can compare with UTC timestamps
    """
    # Create a dummy date in IST
    today = datetime.now().date()
    ist_datetime = IST.localize(datetime.combine(today, time(hour, minute)))

    # Convert to UTC
    utc_datetime = ist_datetime.astimezone(pytz.utc)

    return utc_datetime.time()


# Convenience constants
SCHOOL_START_HOUR_IST = 6  # 6 AM IST
SCHOOL_END_HOUR_IST = 20  # 8 PM IST
BUSINESS_HOURS_START = 9  # 9 AM IST
BUSINESS_HOURS_END = 18  # 6 PM IST
