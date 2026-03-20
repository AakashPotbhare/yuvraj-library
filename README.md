# Yuvraj Library Management System

A simple library management system for Yuvraj Library, Chhatri Chowk, Ujjain.

## Setup (First Time Only)

1. Install Python 3.10 or newer from: https://www.python.org/downloads/
   - On Windows: check "Add Python to PATH" during installation

2. Double-click `run.bat` (Windows) or run `./run.sh` (Mac/Linux)

3. Your browser will open automatically to the library system

That's it! No other software needed.

---

## Daily Use

1. Double-click `run.bat` to start
2. Your browser opens to http://localhost:5000
3. To stop: close the black command window

---

## Features

- **Members** — Register students, professionals, and other members with government ID
- **Books** — Add books with rack/shelf location, category, and number of copies
- **Issue Books** — Issue a book to a member (15-day loan period by default)
- **Return & Reissue** — Return a book or extend the loan by 15 more days
- **Overdue Alerts** — Dashboard shows overdue books at a glance
- **Search** — Find members by name or phone; find books by title, author, or category

---

## Backup (IMPORTANT)

All library data is stored in a single file: **`library.db`**

To backup:
1. Copy `library.db` to a USB drive
2. Keep it somewhere safe

To restore:
1. Copy `library.db` back to this folder
2. Start the app normally

**Recommended:** Back up `library.db` once a week.

---

## Keyboard Guide (for staff)

| Action | Where to go |
|--------|------------|
| Add new member | Members → Add Member |
| Issue a book | Issues → Issue a Book |
| Return a book | Issues → (find the book) → Return |
| See overdue books | Overdue (top menu) |
| Find a member | Members → search by name or phone |
| Find a book | Books → search by title or author |

---

## Technical Notes

- The system runs on your local computer only (no internet needed)
- Port: 5000 (do not change)
- Python 3.10+ required
- Database file: `library.db` (keep this file safe — it contains all your data)
