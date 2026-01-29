from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from db import (
    list_events, get_event, decrement_spots_left,
    create_booking, list_bookings, get_booking,
    update_booking, delete_booking, clear_bookings
)
import db

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"


def parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def fmt_card_dt(s: str) -> str:
    dt = parse_dt(s)
    return dt.strftime("%a, %d %b %Y at %H:%M")


def fmt_details_date(s: str) -> str:
    dt = parse_dt(s)
    return dt.strftime("%A, %d %B %Y")


def fmt_details_time(s: str) -> str:
    dt = parse_dt(s)
    return dt.strftime("%H:%M")

@app.context_processor
def inject_datetime():
    return {"datetime": datetime}

@app.context_processor
def inject_counts():
    return {"booking_count": len(list_bookings())}


@app.get("/")
def home():
    return redirect(url_for("events"))


@app.get("/events")
def events():
    location = request.args.get("location", "").strip()
    from_date = request.args.get("from_date", "").strip()
    to_date = request.args.get("to_date", "").strip()
    activity_type = request.args.get("activity_type", "").strip()

    rows = list_events(
        location=location or None,
        activity_type=activity_type or None,
        from_date=from_date or None,
        to_date=to_date or None
    )

    # format for template
    events = []
    for r in rows:
        e = dict(r)
        e["date_fmt"] = fmt_card_dt(e["date"])
        events.append(e)

    categories = sorted(list({r["category"] for r in list_events()}))

    return render_template("events.html", events=events, categories=categories, filters={
        "location": location,
        "from_date": from_date,
        "to_date": to_date,
        "activity_type": activity_type,
    })

@app.get("/events/<int:event_id>")
def event_details(event_id):
    row = get_event(event_id)
    if not row:
        flash("Event not found.", "danger")
        return redirect(url_for("events"))

    data = dict(row)
    data["date_long"] = fmt_details_date(data["date"])
    data["time_only"] = fmt_details_time(data["date"])
    return render_template("event_details.html", event=data)


@app.get("/events/<int:event_id>/register")
def register_form(event_id):
    row = get_event(event_id)
    if not row:
        flash("Event not found.", "danger")
        return redirect(url_for("events"))

    data = dict(row)
    data["date_long"] = fmt_details_date(data["date"])
    data["time_only"] = fmt_details_time(data["date"])
    return render_template("register_form.html", event=data)



@app.post("/events/<int:event_id>/register")
def register_submit(event_id):
    event = get_event(event_id)
    if not event:
        flash("Event not found.", "danger")
        return redirect(url_for("events"))

    # validate input (same as you have)
    first_name = request.form.get("first_name","").strip()
    last_name = request.form.get("last_name","").strip()
    contact = request.form.get("contact","").strip()
    age_group = request.form.get("age_group","").strip()
    reg_type = request.form.get("reg_type","").strip()
    consent = request.form.get("consent")

    if not first_name or not last_name or not contact or not age_group or not reg_type or consent != "yes":
        flash("Please complete all fields and tick consent.", "danger")
        return redirect(url_for("register_form", event_id=event_id))

    if (not contact.isdigit()) or (len(contact) < 8):
        flash("Contact number must be at least 8 digits.", "danger")
        return redirect(url_for("register_form", event_id=event_id))

    # decrement spots (returns False if no spots)
    if not decrement_spots_left(event_id):
        flash("No spots left for this event.", "danger")
        return redirect(url_for("event_details", event_id=event_id))

    create_booking(
    event_id=event_id,
    first_name=first_name,
    last_name=last_name,
    contact=contact,
    age_group=age_group,
    reg_type=reg_type,
    saved_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
)


    return redirect(url_for("success"))



@app.get("/success")
def success():
    return render_template("success.html")


@app.get("/bookings")
def bookings():
    rows = list_bookings()
    return render_template("bookings.html", bookings=rows)


@app.get("/bookings/<int:booking_id>/edit")
def edit_booking(booking_id):
    b = get_booking(booking_id)
    if not b:
        flash("Booking not found.", "danger")
        return redirect(url_for("bookings"))
    return render_template("edit_booking.html", booking=b)


@app.post("/bookings/<int:booking_id>/edit")
def edit_booking_post(booking_id):
    b = get_booking(booking_id)
    if not b:
        flash("Booking not found.", "danger")
        return redirect(url_for("bookings"))

    # validate + update
    first_name = request.form.get("first_name","").strip()
    last_name  = request.form.get("last_name","").strip()
    contact    = request.form.get("contact","").strip()
    age_group  = request.form.get("age_group","").strip()
    reg_type   = request.form.get("reg_type","").strip()

    if not first_name or not last_name or not contact or not age_group or not reg_type:
        flash("Please fill in all fields.", "danger")
        return redirect(url_for("edit_booking", booking_id=booking_id))
    if (not contact.isdigit()) or (len(contact) < 8):
        flash("Contact number must be at least 8 digits.", "danger")
        return redirect(url_for("edit_booking", booking_id=booking_id))

    update_booking(
    booking_id,
    first_name=first_name,
    last_name=last_name,
    contact=contact,
    age_group=age_group,
    reg_type=reg_type
)

    flash("Booking updated.", "success")
    return redirect(url_for("bookings"))

@app.post("/bookings/<int:booking_id>/delete")
def delete_booking_route(booking_id):
    delete_booking(booking_id)
    flash("Booking deleted.", "info")
    return redirect(url_for("bookings"))

@app.post("/bookings/clear")
def clear_bookings():
    db.clear_bookings()
    flash("Bookings cleared.", "info")
    return redirect(url_for("bookings"))



if __name__ == "__main__":
    app.run(debug=True)
