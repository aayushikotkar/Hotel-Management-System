# Hotel Management System

Frontend: HTML, CSS, JavaScript  
Backend: Python Flask (`main.py`)  
Database: MySQL (use XAMPP / phpMyAdmin)

## Important
- XAMPP is used here for **MySQL + phpMyAdmin**
- Python backend runs separately using Flask
- Start **Apache + MySQL** in XAMPP
- Then run `python main.py`

## Setup steps

### 1) Install packages
```bash
pip install -r requirements.txt
```

### 2) Start XAMPP
Start:
- Apache
- MySQL

### 3) Create database
Open:
```text
http://localhost/phpmyadmin
```

Create a database named:
```text
hotel_management
```

Then import:
```text
hotel_management.sql
```

### 4) Update DB credentials if needed
Open `main.py` and check:
```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "hotel_management"
}
```

### 5) Run the project
```bash
python main.py
```

### 6) Open in browser
```text
http://127.0.0.1:5000
```

## Default admin login
- Username: `admin`
- Password: `admin123`

## Main features
- User registration and login
- Password hashing
- View hotel rooms
- Book a room
- My bookings page
- Contact form
- Admin login
- Admin dashboard
- Add room
- Delete room
- View all bookings
- Approve or reject bookings

## Important note
This is a good working college project. It is not production-level software.
