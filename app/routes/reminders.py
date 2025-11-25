from datetime import datetime, date, time, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db.database import get_db
from app.db.models import Medication, MedicationSchedule, DoseLog
from app.core.auth import get_current_user
import pytz

router = APIRouter()

@router.get("/today")
async def get_todays_reminders(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    tz = pytz.timezone("America/Toronto")  # user timezone (later dynamic)
    today = date.today()

    # Make "now" naive so comparisons always work consistently
    now_naive = datetime.now(tz).replace(tzinfo=None)

    # 1. Fetch schedules + meds
    result = await db.execute(
        select(MedicationSchedule)
        .where(MedicationSchedule.user_id == current_user.user_id)
        .options(selectinload(MedicationSchedule.medication))
    )
    schedules = result.scalars().all()

    reminders = []

    for sched in schedules:
        # Skip days that don't apply
        if not sched.days or today.strftime("%A") not in sched.days:
            continue

        for t in (sched.time_of_day or []):
            # Parse time strings safely (support multiple formats)
            try:
                parsed = parse_time_12h(t)
            except Exception as e:
                # Skip malformed time entries instead of raising a 500
                print(f"⚠️ Skipping invalid scheduled time '{t}' for schedule {sched.id}:", e)
                continue

            # Build scheduled datetime as NAIVE to match DB
            scheduled_dt = datetime(
                today.year, today.month, today.day,
                parsed.hour, parsed.minute
            )

            # 2. Lookup or create dose log
            log_result = await db.execute(
                select(DoseLog).where(
                    DoseLog.user_id == current_user.user_id,
                    DoseLog.schedule_id == sched.id,
                    DoseLog.scheduled_time == scheduled_dt
                )
            )
            log = log_result.scalar_one_or_none()

            if not log:
                log = DoseLog(
                    user_id=current_user.user_id,
                    schedule_id=sched.id,
                    scheduled_time=scheduled_dt,
                    status="pending"
                )
                db.add(log)
                await db.commit()
                await db.refresh(log)

            # 3. Overdue logic using naive datetime
            overdue = log.status == "pending" and now_naive > scheduled_dt

            reminders.append({
                "id": log.id,
                "name": sched.medication.brand_name,
                "strength": sched.strength,
                "quantity": sched.quantity,
                "time": t,
                "status": log.status,
                "overdue": overdue,
                "instructions": sched.food_instructions,
            })

    return reminders


# ---------------- MARK AS TAKEN ----------------
@router.post("/{dose_id}/mark-taken")
async def mark_taken(
    dose_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(DoseLog).where(DoseLog.id == dose_id, DoseLog.user_id == current_user.user_id)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Dose log not found")

    log.status = "taken"
    # model uses `taken_time` column name
    log.taken_time = datetime.utcnow()
    await db.commit()
    await db.refresh(log)

    return {"success": True, "status": log.status}


# ---------------- SNOOZE ----------------
@router.post("/{dose_id}/snooze")
async def snooze_dose(
    dose_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(DoseLog).where(DoseLog.id == dose_id, DoseLog.user_id == current_user.user_id)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Dose log not found")

    # Shift scheduled time forward by 15 minutes (or any business rule)
    log.scheduled_time += timedelta(minutes=15)
    log.status = "snoozed"
    await db.commit()
    await db.refresh(log)

    return {
        "success": True,
        "status": log.status,
        "new_scheduled_time": log.scheduled_time.isoformat()
    }



def parse_time_12h(time_str: str):
    """
    Try several common time formats and return a time object.
    Raises ValueError if no format matches.
    """
    fmts = ["%I:%M %p", "%H:%M", "%I:%M%p", "%I %p"]
    for f in fmts:
        try:
            return datetime.strptime(time_str, f).time()
        except Exception:
            continue
    # As a last resort, try to strip whitespace and lowercase AM/PM spacing issues
    normalized = time_str.replace(".", "").replace("am", " AM").replace("pm", " PM").strip()
    for f in fmts:
        try:
            return datetime.strptime(normalized, f).time()
        except Exception:
            continue
    raise ValueError(f"Unrecognized time format: '{time_str}'")


@router.get("/streak")
async def get_streak(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Compute the current day streak (consecutive days with at least one taken dose)
    and a small 7-day summary. Does not modify the DB schema.
    """
    tz = pytz.timezone("America/Toronto")
    today = datetime.now(tz).date()

    # Look back up to 365 days to build the set of taken dates
    since = datetime.now(tz) - timedelta(days=365)

    result = await db.execute(
        select(DoseLog).where(
            DoseLog.user_id == current_user.user_id,
            DoseLog.status == "taken",
            DoseLog.taken_time != None,
            DoseLog.taken_time >= since,
        )
    )
    logs = result.scalars().all()

    taken_dates: set[date] = set()
    for log in logs:
        if not log.taken_time:
            continue
        taken_at = log.taken_time
        # treat naive datetimes as UTC
        if taken_at.tzinfo is None:
            taken_at = pytz.utc.localize(taken_at)
        local_dt = taken_at.astimezone(tz)
        taken_dates.add(local_dt.date())

    # compute current streak
    streak = 0
    d = today
    while d in taken_dates:
        streak += 1
        d = d - timedelta(days=1)

    # weekly summary (last 7 days)
    weekly = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        weekly.append({"day": day.strftime("%a"), "taken": day in taken_dates})

    return {"current_streak": streak, "weekly": weekly}


@router.get("/summary")
async def get_progress_summary(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Return progress summary for different windows (daily, weekly, monthly).
    Uses existing DoseLog rows to compute taken vs total scheduled doses.
    """
    tz = pytz.timezone("America/Toronto")
    now = datetime.now(tz)

    # Helper to build day boundaries (naive datetimes matching stored scheduled_time)
    def day_bounds(d: date):
        start = datetime(d.year, d.month, d.day, 0, 0, 0)
        end = datetime(d.year, d.month, d.day, 23, 59, 59, 999999)
        return start, end

    # Query logs for last 31 days (covers month window)
    since = (now - timedelta(days=31)).replace(tzinfo=None)
    result = await db.execute(
        select(DoseLog).where(
            DoseLog.user_id == current_user.user_id,
            DoseLog.scheduled_time >= since,
        )
    )
    logs = result.scalars().all()

    # Group logs by date
    by_date: dict[date, list] = {}
    for log in logs:
        sched = log.scheduled_time
        if sched is None:
            continue
        # scheduled_time stored as naive; interpret in server local
        d = sched.date()
        by_date.setdefault(d, []).append(log)

    def compute_window(days_back: int):
        taken = 0
        total = 0
        daily = []
        for i in range(days_back - 1, -1, -1):
            d = (now.date() - timedelta(days=i))
            logs_for_day = by_date.get(d, [])
            day_total = len(logs_for_day)
            day_taken = sum(1 for l in logs_for_day if l.status == "taken")
            total += day_total
            taken += day_taken
            pct = int((day_taken / day_total) * 100) if day_total else None
            daily.append({"day": d.strftime("%a"), "taken": day_taken, "total": day_total, "percentage": pct})
        overall_pct = int((taken / total) * 100) if total else None
        return {"taken": taken, "total": total, "percentage": overall_pct, "daily": daily}

    daily_summary = compute_window(1)
    weekly_summary = compute_window(7)
    monthly_summary = compute_window(30)

    return {
        "daily": daily_summary,
        "weekly": weekly_summary,
        "monthly": monthly_summary,
    }


@router.get("/debug/schedules")
async def debug_schedules(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Return the medication schedules for the current user along with an
    attempted parse result for each time string. Useful for finding malformed
    `time_of_day` entries that could cause runtime errors.
    """
    result = await db.execute(
        select(MedicationSchedule).where(MedicationSchedule.user_id == current_user.user_id).options(selectinload(MedicationSchedule.medication))
    )
    schedules = result.scalars().all()

    out = []
    for s in schedules:
        times = s.time_of_day or []
        parsed = []
        for t in times:
            try:
                p = parse_time_12h(t)
                parsed.append({"raw": t, "ok": True, "parsed": p.strftime("%H:%M")})
            except Exception as e:
                parsed.append({"raw": t, "ok": False, "error": str(e)})

        out.append({
            "schedule_id": s.id,
            "medication": getattr(s.medication, "brand_name", None),
            "time_of_day": times,
            "parsed_times": parsed,
        })

    return {"schedules": out}
