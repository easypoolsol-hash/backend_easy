# Timezone Management Guide

## Industry Best Practice: Store UTC, Display Local

This project follows the **Fortune 500 standard** for timezone management:

1. **Database Storage**: Always UTC (automatic with `USE_TZ=True`)
2. **Business Logic**: Calculate in IST (Indian Standard Time)
3. **API Display**: Show IST to users
4. **Never Repeat**: Use utility functions, not manual conversion

## Quick Reference

```python
from utils.timezone_utils import (
    get_current_time_ist,
    get_start_of_day_ist,
    get_end_of_day_ist,
    to_ist,
    is_within_school_hours
)
```

---

## Common Scenarios

### Scenario 1: Get Today's Events (in IST)

**❌ WRONG WAY** (Timezone bug - gets wrong day):
```python
# DON'T DO THIS - Uses UTC midnight, not IST midnight
from django.utils import timezone

today = timezone.now().date()
events = BoardingEvent.objects.filter(
    boarded_at__date=today  # BUG: This is UTC date!
)
```

**✅ CORRECT WAY**:
```python
from utils.timezone_utils import get_time_range_today_ist

# Get today's range in IST (automatically converted to UTC for query)
start, end = get_time_range_today_ist()
events = BoardingEvent.objects.filter(
    boarded_at__gte=start,
    boarded_at__lte=end
)
```

**Why it matters**: If it's 1:00 AM IST (Jan 16), it's still 7:30 PM UTC (Jan 15). Using UTC date would get the wrong day's events!

---

### Scenario 2: Check If Within School Hours

**❌ WRONG WAY** (Sends notifications at 2 AM IST!):
```python
from django.utils import timezone

now = timezone.now()
if 6 <= now.hour <= 20:  # BUG: Checking UTC hour!
    send_notification()
```

**✅ CORRECT WAY**:
```python
from utils.timezone_utils import is_within_school_hours

if is_within_school_hours():  # Checks IST hours
    send_notification()
```

---

### Scenario 3: Display Time in API Response

**❌ WRONG WAY** (Shows UTC to Indian users):
```python
class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoardingEvent
        fields = ['id', 'student_name', 'boarded_at']

# Response shows: "boarded_at": "2024-01-15T10:00:00Z"  ← Confusing for users!
```

**✅ CORRECT WAY** (Option A - Manual):
```python
from utils.timezone_utils import to_ist

class EventSerializer(serializers.ModelSerializer):
    boarded_at_ist = serializers.SerializerMethodField()

    class Meta:
        model = BoardingEvent
        fields = ['id', 'student_name', 'boarded_at', 'boarded_at_ist']

    def get_boarded_at_ist(self, obj):
        return to_ist(obj.boarded_at).isoformat()

# Response:
# "boarded_at": "2024-01-15T10:00:00Z",        ← UTC for backend
# "boarded_at_ist": "2024-01-15T15:30:00+05:30"  ← IST for display
```

**✅ CORRECT WAY** (Option B - Mixin, DRY):
```python
from utils.serializer_mixins import ISTTimezoneMixin

class EventSerializer(ISTTimezoneMixin, serializers.ModelSerializer):
    class Meta:
        model = BoardingEvent
        fields = ['id', 'student_name', 'boarded_at', 'boarded_at_ist']
        ist_fields = ['boarded_at']  # Automatically adds '_ist' field
```

---

### Scenario 4: Schedule Comparison (Bus Routes)

**❌ WRONG WAY**:
```python
# Route schedule stored as: {"morning": {"start": "07:00", "end": "09:00"}}
from django.utils import timezone

now = timezone.now()
current_time_str = now.strftime("%H:%M")
if "07:00" <= current_time_str <= "09:00":  # BUG: Comparing UTC time!
    # Bus should be running
    pass
```

**✅ CORRECT WAY**:
```python
from utils.timezone_utils import get_current_time_ist

now_ist = get_current_time_ist()
current_time_str = now_ist.strftime("%H:%M")
if "07:00" <= current_time_str <= "09:00":  # IST comparison
    # Bus should be running
    pass
```

---

### Scenario 5: Creating Events with IST Input

**❌ WRONG WAY** (User enters "3:30 PM" but stored as UTC!):
```python
from datetime import datetime

# User inputs: "15:30" (3:30 PM IST)
user_input_time = datetime.strptime("15:30", "%H:%M").time()
event = BoardingEvent.objects.create(
    boarded_at=datetime.combine(date.today(), user_input_time)
    # BUG: Interpreted as UTC, not IST!
)
```

**✅ CORRECT WAY**:
```python
from datetime import datetime
from utils.timezone_utils import to_utc, IST

# User inputs: "15:30" (3:30 PM IST)
user_input_time = datetime.strptime("15:30", "%H:%M").time()

# Localize to IST first
ist_datetime = IST.localize(datetime.combine(date.today(), user_input_time))

# Convert to UTC for storage
event = BoardingEvent.objects.create(
    boarded_at=to_utc(ist_datetime)
)
```

---

### Scenario 6: Filtering by Time Range

**Example: Get all events between 7 AM and 9 AM IST today**

**✅ CORRECT WAY**:
```python
from datetime import time
from utils.timezone_utils import get_start_of_day_ist, ist_time_to_utc_time, IST

# Define IST time range
ist_start_time = time(7, 0)   # 7:00 AM IST
ist_end_time = time(9, 0)     # 9:00 AM IST

# Get today in IST
today_start_ist = get_start_of_day_ist()

# Combine date with time
from datetime import datetime
start_datetime_ist = IST.localize(
    datetime.combine(today_start_ist.date(), ist_start_time)
)
end_datetime_ist = IST.localize(
    datetime.combine(today_start_ist.date(), ist_end_time)
)

# Convert to UTC for query
from utils.timezone_utils import to_utc
start_utc = to_utc(start_datetime_ist)
end_utc = to_utc(end_datetime_ist)

# Query
morning_events = BoardingEvent.objects.filter(
    boarded_at__gte=start_utc,
    boarded_at__lte=end_utc
)
```

---

## Real-World Example: Dashboard Stats

**Problem**: Show "Students Boarded Today" on school dashboard.

**✅ CORRECT IMPLEMENTATION**:

```python
# In views.py
from utils.timezone_utils import get_time_range_today_ist

def dashboard_view(request):
    # Get today's range in IST (7 AM - 8 PM school day)
    today_start, today_end = get_time_range_today_ist()

    # Count students boarded today (IST day, not UTC day)
    students_boarded_today = BoardingEvent.objects.filter(
        boarded_at__gte=today_start,
        boarded_at__lte=today_end,
        event_type='BOARD'
    ).count()

    return JsonResponse({
        'students_boarded_today': students_boarded_today,
        'date': today_start.astimezone(IST).date().isoformat()
    })
```

---

## Testing Timezone Logic

**✅ CORRECT WAY**:

```python
# In tests
from datetime import datetime, timedelta
from django.utils import timezone
from utils.timezone_utils import IST, to_utc, get_start_of_day_ist
import pytest


@pytest.mark.django_db
class TestTimezoneLogic:
    def test_today_events_at_midnight_ist(self):
        """Test that events created at IST midnight are counted in correct day."""
        # Create event at 00:30 IST (which is 19:00 UTC previous day)
        ist_time = IST.localize(datetime(2024, 1, 16, 0, 30))

        event = BoardingEvent.objects.create(
            student=student,
            boarded_at=to_utc(ist_time)  # Converts to UTC for storage
        )

        # Query for Jan 16 IST
        target_date = datetime(2024, 1, 16)
        start = get_start_of_day_ist(target_date)
        end = get_end_of_day_ist(target_date)

        events = BoardingEvent.objects.filter(
            boarded_at__gte=start,
            boarded_at__lte=end
        )

        assert event in events  # Should be found in Jan 16 IST day

    def test_school_hours_check(self):
        """Test that school hours check uses IST, not UTC."""
        from utils.timezone_utils import is_within_school_hours

        # Create time at 7:30 AM IST (which is 2:00 AM UTC)
        ist_morning = IST.localize(datetime(2024, 1, 16, 7, 30))

        assert is_within_school_hours(ist_morning) is True

        # Create time at 2:00 AM IST (outside school hours)
        ist_night = IST.localize(datetime(2024, 1, 16, 2, 0))

        assert is_within_school_hours(ist_night) is False
```

---

## Migration Strategy

If you have existing code that doesn't handle timezones correctly:

1. **Find all timezone-related code**:
   ```bash
   grep -r "timezone.now()" app/
   grep -r "\.date()" app/
   grep -r "\.hour" app/
   grep -r "strftime" app/
   ```

2. **Replace with utility functions**:
   - `timezone.now()` for display → `get_current_time_ist()`
   - Date comparisons → `get_start_of_day_ist()` / `get_end_of_day_ist()`
   - Hour comparisons → `is_within_school_hours()`

3. **Add IST fields to serializers**:
   - Use `ISTTimezoneMixin` for automatic conversion
   - Or manually add `SerializerMethodField` with `to_ist()`

4. **Test thoroughly**:
   - Test at IST midnight (19:00 UTC)
   - Test at UTC midnight (05:30 IST)
   - Test during school hours
   - Test outside school hours

---

## Common Pitfalls to Avoid

### ❌ Pitfall 1: Using `.date()` on UTC datetime
```python
# WRONG - Gets UTC date, not IST date
from django.utils import timezone
today = timezone.now().date()
```

### ❌ Pitfall 2: Comparing time strings without timezone context
```python
# WRONG - Compares UTC hour with IST schedule
now = timezone.now()
if now.hour >= 7:  # Is this UTC 7 or IST 7?
```

### ❌ Pitfall 3: Hardcoding timezone offsets
```python
# WRONG - IST offset can change (DST), use pytz
ist_time = utc_time + timedelta(hours=5, minutes=30)
```

### ❌ Pitfall 4: Mixing naive and aware datetimes
```python
# WRONG - Comparing naive and aware datetimes
naive_dt = datetime(2024, 1, 15, 10, 0)
aware_dt = timezone.now()
if naive_dt > aware_dt:  # ERROR or wrong result
```

---

## Configuration Checklist

✅ `USE_TZ = True` in settings.py (Already set)
✅ `TIME_ZONE = "UTC"` in settings.py (Already set)
✅ Use `timezone_utils.py` for all timezone operations
✅ Use `ISTTimezoneMixin` in serializers
✅ Test timezone logic thoroughly

---

## References

- Django Timezone Documentation: https://docs.djangoproject.com/en/stable/topics/i18n/timezones/
- pytz Documentation: https://pythonhosted.org/pytz/
- Industry Standard: Stripe, Google, AWS all use UTC storage + local display
