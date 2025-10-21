"""
Unit tests for timezone utilities.

Tests the industry-standard timezone conversion logic.
"""

from datetime import datetime

from django.utils import timezone
import pytz
from utils.timezone_utils import (
    IST,
    format_datetime_ist,
    get_current_time_ist,
    get_end_of_day_ist,
    get_start_of_day_ist,
    get_time_range_today_ist,
    is_within_school_hours,
    ist_time_to_utc_time,
    to_ist,
    to_utc,
)


class TestTimezoneConversions:
    """Test basic timezone conversion functions."""

    def test_to_ist_converts_utc_to_ist(self):
        """Test that UTC datetime is correctly converted to IST."""
        # Create UTC time: Jan 15, 2024 10:00:00 UTC
        utc_time = timezone.make_aware(datetime(2024, 1, 15, 10, 0, 0), pytz.utc)

        # Convert to IST
        ist_time = to_ist(utc_time)

        # Should be Jan 15, 2024 15:30:00 IST (UTC+5:30)
        assert ist_time.year == 2024
        assert ist_time.month == 1
        assert ist_time.day == 15
        assert ist_time.hour == 15
        assert ist_time.minute == 30
        assert ist_time.second == 0
        assert str(ist_time.tzinfo) == "Asia/Kolkata"

    def test_to_ist_handles_naive_datetime(self):
        """Test that naive datetime is treated as UTC."""
        # Create naive datetime
        naive_time = datetime(2024, 1, 15, 10, 0, 0)

        # Should treat as UTC and convert to IST
        ist_time = to_ist(naive_time)

        assert ist_time.hour == 15  # 10:00 UTC = 15:30 IST
        assert ist_time.minute == 30

    def test_to_ist_handles_none(self):
        """Test that None is handled gracefully."""
        assert to_ist(None) is None

    def test_to_utc_converts_ist_to_utc(self):
        """Test that IST datetime is correctly converted to UTC."""
        # Create IST time: Jan 15, 2024 15:30:00 IST
        ist_time = IST.localize(datetime(2024, 1, 15, 15, 30, 0))

        # Convert to UTC
        utc_time = to_utc(ist_time)

        # Should be Jan 15, 2024 10:00:00 UTC
        assert utc_time.year == 2024
        assert utc_time.month == 1
        assert utc_time.day == 15
        assert utc_time.hour == 10
        assert utc_time.minute == 0
        assert utc_time.tzinfo == pytz.utc

    def test_to_utc_handles_naive_datetime(self):
        """Test that naive datetime is treated as IST."""
        # Create naive datetime (assumed IST)
        naive_time = datetime(2024, 1, 15, 15, 30, 0)

        # Should treat as IST and convert to UTC
        utc_time = to_utc(naive_time)

        assert utc_time.hour == 10  # 15:30 IST = 10:00 UTC
        assert utc_time.minute == 0

    def test_to_utc_handles_none(self):
        """Test that None is handled gracefully."""
        assert to_utc(None) is None

    def test_roundtrip_conversion(self):
        """Test that UTC -> IST -> UTC preserves the time."""
        original_utc = timezone.make_aware(datetime(2024, 1, 15, 10, 0, 0), pytz.utc)

        # Convert to IST and back
        ist_time = to_ist(original_utc)
        back_to_utc = to_utc(ist_time)

        # Should be equal (accounting for timezone info)
        assert back_to_utc.replace(tzinfo=None) == original_utc.replace(tzinfo=None)


class TestCurrentTime:
    """Test current time retrieval."""

    def test_get_current_time_ist_returns_ist_timezone(self):
        """Test that current time is returned in IST."""
        current = get_current_time_ist()

        assert str(current.tzinfo) == "Asia/Kolkata"

    def test_get_current_time_ist_is_close_to_now(self):
        """Test that current IST time is close to actual now."""
        current_ist = get_current_time_ist()
        now_utc = timezone.now()
        now_ist = to_ist(now_utc)

        # Should be within 1 second
        diff = abs((current_ist - now_ist).total_seconds())
        assert diff < 1


class TestDayBoundaries:
    """Test start/end of day calculations."""

    def test_get_start_of_day_ist_for_specific_date(self):
        """Test start of day for a specific date."""
        # Jan 15, 2024 in IST
        target_date = IST.localize(datetime(2024, 1, 15, 12, 0, 0))

        start = get_start_of_day_ist(target_date)

        # Should be Jan 15, 2024 00:00:00 IST converted to UTC
        # Which is Jan 14, 2024 18:30:00 UTC
        assert start.astimezone(IST).year == 2024
        assert start.astimezone(IST).month == 1
        assert start.astimezone(IST).day == 15
        assert start.astimezone(IST).hour == 0
        assert start.astimezone(IST).minute == 0
        assert start.astimezone(IST).second == 0

    def test_get_end_of_day_ist_for_specific_date(self):
        """Test end of day for a specific date."""
        # Jan 15, 2024 in IST
        target_date = IST.localize(datetime(2024, 1, 15, 12, 0, 0))

        end = get_end_of_day_ist(target_date)

        # Should be Jan 15, 2024 23:59:59.999999 IST
        assert end.astimezone(IST).year == 2024
        assert end.astimezone(IST).month == 1
        assert end.astimezone(IST).day == 15
        assert end.astimezone(IST).hour == 23
        assert end.astimezone(IST).minute == 59

    def test_get_start_of_day_ist_defaults_to_today(self):
        """Test that start of day defaults to today."""
        start = get_start_of_day_ist()
        now_ist = get_current_time_ist()

        assert start.astimezone(IST).date() == now_ist.date()
        assert start.astimezone(IST).hour == 0

    def test_get_time_range_today_ist(self):
        """Test getting today's time range."""
        start, end = get_time_range_today_ist()

        # Start should be 00:00:00 IST today
        # End should be 23:59:59 IST today
        now_ist = get_current_time_ist()

        assert start.astimezone(IST).date() == now_ist.date()
        assert end.astimezone(IST).date() == now_ist.date()
        assert start.astimezone(IST).hour == 0
        assert end.astimezone(IST).hour == 23

    def test_day_boundary_edge_case_ist_midnight(self):
        """Test edge case at IST midnight (18:30 UTC)."""
        # IST midnight is 18:30 UTC previous day
        # Jan 16, 2024 00:00:00 IST = Jan 15, 2024 18:30:00 UTC
        ist_midnight = IST.localize(datetime(2024, 1, 16, 0, 0, 0))

        start = get_start_of_day_ist(ist_midnight)

        # Should get start of Jan 16 IST
        assert start.astimezone(IST).date() == datetime(2024, 1, 16).date()


class TestSchoolHours:
    """Test school hours checking."""

    def test_is_within_school_hours_morning(self):
        """Test time within school hours (morning)."""
        # 7:30 AM IST
        morning = IST.localize(datetime(2024, 1, 15, 7, 30, 0))

        assert is_within_school_hours(morning) is True

    def test_is_within_school_hours_afternoon(self):
        """Test time within school hours (afternoon)."""
        # 3:00 PM IST
        afternoon = IST.localize(datetime(2024, 1, 15, 15, 0, 0))

        assert is_within_school_hours(afternoon) is True

    def test_is_within_school_hours_early_morning(self):
        """Test time before school hours."""
        # 5:00 AM IST (before 6 AM)
        early = IST.localize(datetime(2024, 1, 15, 5, 0, 0))

        assert is_within_school_hours(early) is False

    def test_is_within_school_hours_late_night(self):
        """Test time after school hours."""
        # 10:00 PM IST (after 8 PM)
        late = IST.localize(datetime(2024, 1, 15, 22, 0, 0))

        assert is_within_school_hours(late) is False

    def test_is_within_school_hours_custom_range(self):
        """Test with custom school hours."""
        # 9:00 AM IST
        time_9am = IST.localize(datetime(2024, 1, 15, 9, 0, 0))

        # Custom hours: 8 AM to 6 PM
        assert is_within_school_hours(time_9am, start_hour=8, end_hour=18) is True

        # Outside custom hours
        assert is_within_school_hours(time_9am, start_hour=10, end_hour=18) is False

    def test_is_within_school_hours_defaults_to_now(self):
        """Test that it defaults to current time."""
        # Just check it doesn't error
        result = is_within_school_hours()
        assert isinstance(result, bool)


class TestTimeFormatting:
    """Test datetime formatting."""

    def test_format_datetime_ist_default_format(self):
        """Test default datetime formatting."""
        utc_time = timezone.make_aware(datetime(2024, 1, 15, 10, 0, 0), pytz.utc)

        formatted = format_datetime_ist(utc_time)

        # Should show IST time with timezone
        assert "2024-01-15" in formatted
        assert "15:30:00" in formatted
        assert "IST" in formatted

    def test_format_datetime_ist_custom_format(self):
        """Test custom datetime formatting."""
        utc_time = timezone.make_aware(datetime(2024, 1, 15, 10, 0, 0), pytz.utc)

        formatted = format_datetime_ist(utc_time, "%d-%m-%Y %H:%M")

        # Should show IST time in custom format
        assert formatted == "15-01-2024 15:30"

    def test_format_datetime_ist_handles_none(self):
        """Test that None is handled gracefully."""
        assert format_datetime_ist(None) is None


class TestTimeConversion:
    """Test time-only conversion (for schedules)."""

    def test_ist_time_to_utc_time(self):
        """Test converting IST time to UTC time."""
        # 7:30 AM IST should be 2:00 AM UTC
        utc_time = ist_time_to_utc_time(7, 30)

        assert utc_time.hour == 2
        assert utc_time.minute == 0

    def test_ist_time_to_utc_time_midnight(self):
        """Test midnight conversion."""
        # 00:00 IST should be 18:30 UTC (previous day conceptually)
        utc_time = ist_time_to_utc_time(0, 0)

        # On the same date reference, should be 18:30
        assert utc_time.hour == 18
        assert utc_time.minute == 30

    def test_ist_time_to_utc_time_noon(self):
        """Test noon conversion."""
        # 12:00 IST should be 6:30 UTC
        utc_time = ist_time_to_utc_time(12, 0)

        assert utc_time.hour == 6
        assert utc_time.minute == 30


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_scenario_count_events_today(self):
        """
        Scenario: Count events that happened "today" in IST.
        Critical for dashboard statistics.
        """
        # Simulate: It's Jan 16, 2024 00:30 AM IST
        # This is Jan 15, 2024 19:00 UTC
        current_time_ist = IST.localize(datetime(2024, 1, 16, 0, 30, 0))

        # Get today's range
        start = get_start_of_day_ist(current_time_ist)
        end = get_end_of_day_ist(current_time_ist)

        # Verify the range covers Jan 16 IST
        assert start.astimezone(IST).date() == datetime(2024, 1, 16).date()
        assert end.astimezone(IST).date() == datetime(2024, 1, 16).date()

        # The UTC range should span across UTC dates
        # Start: Jan 15 18:30 UTC
        # End: Jan 16 18:29 UTC
        assert start.astimezone(pytz.utc).date() == datetime(2024, 1, 15).date()
        assert end.astimezone(pytz.utc).date() == datetime(2024, 1, 16).date()

    def test_scenario_schedule_comparison(self):
        """
        Scenario: Check if bus should be running based on IST schedule.
        """
        # Bus schedule: 7:00 AM - 9:00 AM IST
        schedule_start = ist_time_to_utc_time(7, 0)
        schedule_end = ist_time_to_utc_time(9, 0)

        # Current time: 7:30 AM IST
        current_ist = IST.localize(datetime(2024, 1, 15, 7, 30, 0))
        current_utc = to_utc(current_ist)
        current_time = current_utc.time()

        # Compare in UTC
        assert schedule_start <= current_time <= schedule_end

    def test_scenario_notification_timing(self):
        """
        Scenario: Only send notifications during school hours.
        """
        # 2:00 AM IST - should NOT send
        middle_of_night_ist = IST.localize(datetime(2024, 1, 15, 2, 0, 0))
        assert is_within_school_hours(middle_of_night_ist) is False

        # 8:00 AM IST - should send
        morning_ist = IST.localize(datetime(2024, 1, 15, 8, 0, 0))
        assert is_within_school_hours(morning_ist) is True

        # 10:00 PM IST - should NOT send
        night_ist = IST.localize(datetime(2024, 1, 15, 22, 0, 0))
        assert is_within_school_hours(night_ist) is False
