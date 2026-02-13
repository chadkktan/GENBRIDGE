from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from flask import render_template, request, redirect, url_for, flash

from user import is_logged_in
from events_db import (
    list_events,
    get_event,
    decrement_spots_left,
    create_booking,
    list_bookings,
    get_booking,
    update_booking,
    delete_booking,
    clear_bookings as db_clear_bookings,
)


# -----------------------------
# Helpers
# -----------------------------
def _parse_db_datetime(dt_str: str) -> datetime | None:
    """DB stores date as 'YYYY-MM-DD HH:MM'."""
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    except Exception:
        return None


def enrich_datetime_fields(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Adds common display fields for templates."""
    dt = _parse_db_datetime(obj.get("date", ""))
    if dt:
        obj["date_long"] = dt.strftime("%a, %d %b %Y")
        obj["time_only"] = dt.strftime("%H:%M")
        obj["date_fmt"] = dt.strftime("%a, %d %b %Y at %H:%M")
    else:
        obj["date_long"] = obj.get("date", "")
        obj["time_only"] = ""
        obj["date_fmt"] = obj.get("date", "")
    return obj


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# -----------------------------
# Route registrar
# -----------------------------
def register_event_routes(app):
    # Events landing
    @app.get("/events")
    def events():
        if not is_logged_in():
            return redirect(url_for("create_account"))

        filters = {
            "location": request.args.get("location", "").strip(),
            "from_date": request.args.get("from_date", "").strip(),
            "to_date": request.args.get("to_date", "").strip(),
            "activity_type": request.args.get("activity_type", "").strip(),
        }

        evs = list_events(
            location=filters["location"],
            from_date=filters["from_date"],
            to_date=filters["to_date"],
            activity_type=filters["activity_type"],
        )

        for e in evs:
            enrich_datetime_fields(e)

        categories = sorted({e.get("category", "") for e in evs if e.get("category")})

        return render_template(
            "events/events.html",
            events=evs,
            categories=categories,
            filters=filters,
        )


    @app.get("/events/<int:event_id>")
    def event_details(event_id: int):
        if not is_logged_in():
            return redirect(url_for("create_account"))

        ev = get_event(event_id)
        if not ev:
            flash("Event not found.", "danger")
            return redirect(url_for("events"))

        enrich_datetime_fields(ev)
        return render_template("events/event_details.html", event=ev)


    @app.get("/events/<int:event_id>/register")
    def register_form(event_id: int):
        if not is_logged_in():
            return redirect(url_for("create_account"))

        ev = get_event(event_id)
        if not ev:
            flash("Event not found.", "danger")
            return redirect(url_for("events"))

        enrich_datetime_fields(ev)
        return render_template("events/register_form.html", event=ev)


    @app.post("/events/<int:event_id>/register")
    def register_submit(event_id: int):
        if not is_logged_in():
            return redirect(url_for("create_account"))

        ev = get_event(event_id)
        if not ev:
            flash("Event not found.", "danger")
            return redirect(url_for("events"))

        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        contact = request.form.get("contact", "").strip()
        age_group = request.form.get("age_group", "").strip()
        reg_type = request.form.get("reg_type", "").strip()

        consent = request.form.get("consent", "").strip()

        if not first_name or not last_name or not contact or not age_group or not reg_type:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("register_form", event_id=event_id))

        if "consent" in request.form and not consent:
            flash("Please agree to the consent checkbox.", "danger")
            return redirect(url_for("register_form", event_id=event_id))

        if (not contact.isdigit()) or (len(contact) < 8):
            flash("Contact number must be at least 8 digits (numbers only).", "danger")
            return redirect(url_for("register_form", event_id=event_id))

        ok = decrement_spots_left(event_id)
        if not ok:
            flash("Sorry! This event is fully booked.", "danger")
            return redirect(url_for("event_details", event_id=event_id))

        create_booking(
            event_id=event_id,
            first_name=first_name,
            last_name=last_name,
            contact=contact,
            age_group=age_group,
            reg_type=reg_type,
            saved_at=now_str(),
        )

        return render_template("events/success.html")


    @app.get("/bookings")
    def bookings():
        if not is_logged_in():
            return redirect(url_for("create_account"))

        items = list_bookings()
        for b in items:
            enrich_datetime_fields(b)
        return render_template("events/bookings.html", bookings=items)


    @app.get("/bookings/<int:booking_id>/edit")
    def edit_booking(booking_id: int):
        if not is_logged_in():
            return redirect(url_for("create_account"))

        booking = get_booking(booking_id)
        if not booking:
            flash("Booking not found.", "danger")
            return redirect(url_for("bookings"))

        return render_template("events/edit_booking.html", booking=booking)


    @app.post("/bookings/<int:booking_id>/edit")
    def edit_booking_post(booking_id: int):
        if not is_logged_in():
            return redirect(url_for("create_account"))

        booking = get_booking(booking_id)
        if not booking:
            flash("Booking not found.", "danger")
            return redirect(url_for("bookings"))

        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        contact = request.form.get("contact", "").strip()
        age_group = request.form.get("age_group", "").strip()
        reg_type = request.form.get("reg_type", "").strip()

        if not first_name or not last_name or not contact or not age_group or not reg_type:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("edit_booking", booking_id=booking_id))

        if (not contact.isdigit()) or (len(contact) < 8):
            flash("Contact number must be at least 8 digits (numbers only).", "danger")
            return redirect(url_for("edit_booking", booking_id=booking_id))

        ok = update_booking(
            booking_id,
            first_name=first_name,
            last_name=last_name,
            contact=contact,
            age_group=age_group,
            reg_type=reg_type,
        )

        if not ok:
            flash("Failed to update booking.", "danger")
            return redirect(url_for("edit_booking", booking_id=booking_id))

        flash("Booking updated successfully!", "success")
        return redirect(url_for("bookings"))


    @app.post("/bookings/<int:booking_id>/delete")
    def delete_booking_route(booking_id: int):
        if not is_logged_in():
            return redirect(url_for("create_account"))

        ok = delete_booking(booking_id)
        if ok:
            flash("Booking deleted.", "success")
        else:
            flash("Booking not found.", "danger")
        return redirect(url_for("bookings"))


    @app.post("/bookings/clear")
    def clear_bookings():
        if not is_logged_in():
            return redirect(url_for("create_account"))

        db_clear_bookings()
        flash("All bookings cleared.", "success")
        return redirect(url_for("bookings"))
