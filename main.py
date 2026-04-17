from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change_this_to_a_random_secret_key"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "hotel_management"
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def fetch_all(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result


def fetch_one(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result


def execute_query(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    conn.commit()
    cursor.close()
    conn.close()


def admin_required():
    return "admin_id" in session


def user_required():
    return "user_id" in session


@app.context_processor
def inject_today():
    return {"today_date": date.today().isoformat()}


@app.route("/")
def index():
    try:
        rooms = fetch_all("SELECT * FROM rooms ORDER BY id ASC LIMIT 3")
        return render_template("index.html", rooms=rooms)
    except Error as e:
        return f"<h2>Database connection error</h2><p>{e}</p><p>Please import hotel_management.sql and check MySQL settings in main.py.</p>"


@app.route("/rooms")
def rooms():
    rooms = fetch_all("SELECT * FROM rooms ORDER BY id DESC")
    for room in rooms:
        reviews = fetch_all("SELECT r.*, u.full_name FROM reviews r JOIN users u ON r.user_id = u.id WHERE r.room_id=%s ORDER BY r.created_at DESC", (room['id'],))
        room['reviews'] = reviews
    return render_template("rooms.html", rooms=rooms)

@app.route("/add-review/<int:room_id>", methods=["POST"])
def add_review(room_id):
    if not user_required():
        flash("Please login to add a review.", "error")
        return redirect(url_for("login"))
    
    rating = request.form.get("rating")
    comment = request.form.get("comment", "").strip()
    
    if rating:
        execute_query(
            "INSERT INTO reviews (user_id, room_id, rating, comment) VALUES (%s, %s, %s, %s)",
            (session["user_id"], room_id, rating, comment)
        )
        flash("Review added successfully.", "success")
    
    return redirect(url_for("rooms"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip().lower()
        phone = request.form["phone"].strip()
        password = request.form["password"]

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("register"))

        existing = fetch_one("SELECT id FROM users WHERE email=%s", (email,))
        if existing:
            flash("Email already registered.", "error")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        execute_query(
            "INSERT INTO users (full_name, email, phone, password) VALUES (%s, %s, %s, %s)",
            (full_name, email, phone, hashed_password)
        )
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = fetch_one("SELECT * FROM users WHERE email=%s", (email,))
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            flash("Login successful.", "success")
            return redirect(url_for("index"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("index"))


@app.route("/booking/<int:room_id>", methods=["GET", "POST"])
def booking(room_id):
    if not user_required():
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    room = fetch_one("SELECT * FROM rooms WHERE id=%s", (room_id,))
    if not room:
        flash("Room not found.", "error")
        return redirect(url_for("rooms"))

    if request.method == "POST":
        check_in = request.form["check_in"]
        check_out = request.form["check_out"]
        adults = int(request.form["adults"])
        children = int(request.form["children"])

        d1 = datetime.strptime(check_in, "%Y-%m-%d")
        d2 = datetime.strptime(check_out, "%Y-%m-%d")
        days = (d2 - d1).days

        if days <= 0:
            flash("Check-out must be after check-in.", "error")
            return redirect(url_for("booking", room_id=room_id))

        if room["status"] != "Available":
            flash("This room is currently not available.", "error")
            return redirect(url_for("rooms"))

        total_amount = days * float(room["price"])

        coupon_code = request.form.get("coupon_code", "").strip()
        if coupon_code:
            coupon = fetch_one("SELECT * FROM coupons WHERE code=%s AND is_active=1 AND expiry_date >= CURDATE()", (coupon_code,))
            if coupon:
                discount = float(coupon["discount_percent"])
                total_amount = total_amount - (total_amount * discount / 100)
                flash(f"Coupon {coupon_code} applied! {discount}% off.", "success")
            else:
                flash("Invalid or expired coupon applied - proceeding without discount.", "error")

        execute_query(
            """INSERT INTO bookings
               (user_id, room_id, check_in, check_out, adults, children, total_amount, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (session["user_id"], room_id, check_in, check_out, adults, children, total_amount, "Pending")
        )

        flash("Booking submitted successfully.", "success")
        return redirect(url_for("my_bookings"))

    return render_template("booking.html", room=room)


@app.route("/my-bookings")
def my_bookings():
    if not user_required():
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    bookings = fetch_all(
        """SELECT b.*, r.room_name, r.room_type, r.price
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           WHERE b.user_id = %s
           ORDER BY b.created_at DESC""",
        (session["user_id"],)
    )
    return render_template("my_bookings.html", bookings=bookings)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        subject = request.form["subject"].strip()
        message = request.form["message"].strip()

        execute_query(
            "INSERT INTO contact_messages (name, email, subject, message) VALUES (%s, %s, %s, %s)",
            (name, email, subject, message)
        )
        flash("Message sent successfully.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        admin = fetch_one("SELECT * FROM admins WHERE username=%s", (username,))
        if admin and admin["password"] == password:
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            flash("Admin login successful.", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials.", "error")
        return redirect(url_for("admin_login"))

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))

    total_users = fetch_one("SELECT COUNT(*) AS c FROM users")["c"]
    total_rooms = fetch_one("SELECT COUNT(*) AS c FROM rooms")["c"]
    total_bookings = fetch_one("SELECT COUNT(*) AS c FROM bookings")["c"]
    total_messages = fetch_one("SELECT COUNT(*) AS c FROM contact_messages")["c"]

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_rooms=total_rooms,
        total_bookings=total_bookings,
        total_messages=total_messages
    )


@app.route("/admin/rooms", methods=["GET", "POST"])
def manage_rooms():
    if not admin_required():
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        room_name = request.form["room_name"].strip()
        room_type = request.form["room_type"].strip()
        price = request.form["price"].strip()
        capacity = request.form["capacity"].strip()
        image = request.form["image"].strip()
        description = request.form["description"].strip()
        status = request.form["status"].strip()

        execute_query(
            """INSERT INTO rooms (room_name, room_type, price, capacity, image, description, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (room_name, room_type, price, capacity, image, description, status)
        )
        flash("Room added successfully.", "success")
        return redirect(url_for("manage_rooms"))

    rooms = fetch_all("SELECT * FROM rooms ORDER BY id DESC")
    return render_template("manage_rooms.html", rooms=rooms)


@app.route("/admin/delete-room/<int:room_id>")
def delete_room(room_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    execute_query("DELETE FROM rooms WHERE id=%s", (room_id,))
    flash("Room deleted successfully.", "success")
    return redirect(url_for("manage_rooms"))


@app.route("/admin/bookings")
def manage_bookings():
    if not admin_required():
        return redirect(url_for("admin_login"))

    bookings = fetch_all(
        """SELECT b.*, u.full_name, r.room_name
           FROM bookings b
           JOIN users u ON b.user_id = u.id
           JOIN rooms r ON b.room_id = r.id
           ORDER BY b.created_at DESC"""
    )
    return render_template("manage_bookings.html", bookings=bookings)


@app.route("/admin/update-booking-status/<int:booking_id>/<status>")
def update_booking_status(booking_id, status):
    if not admin_required():
        return redirect(url_for("admin_login"))

    if status not in ["Approved", "Rejected", "Pending"]:
        flash("Invalid status.", "error")
        return redirect(url_for("manage_bookings"))

    execute_query("UPDATE bookings SET status=%s WHERE id=%s", (status, booking_id))
    flash(f"Booking status changed to {status}.", "success")
    return redirect(url_for("manage_bookings"))


@app.route("/admin/staff", methods=["GET", "POST"])
def manage_staff():
    if not admin_required():
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        role = request.form["role"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()
        salary = request.form["salary"].strip()
        hire_date = request.form["hire_date"]

        execute_query(
            """INSERT INTO staff (full_name, role, email, phone, salary, hire_date)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (full_name, role, email, phone, salary, hire_date)
        )
        flash("Staff added successfully.", "success")
        return redirect(url_for("manage_staff"))

    staff = fetch_all("SELECT * FROM staff ORDER BY id DESC")
    return render_template("manage_staff.html", staff=staff)


@app.route("/admin/delete-staff/<int:staff_id>")
def delete_staff(staff_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    execute_query("DELETE FROM staff WHERE id=%s", (staff_id,))
    flash("Staff deleted successfully.", "success")
    return redirect(url_for("manage_staff"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    flash("Admin logged out.", "success")
    return redirect(url_for("admin_login"))


if __name__ == "__main__":
    app.run(debug=True)
