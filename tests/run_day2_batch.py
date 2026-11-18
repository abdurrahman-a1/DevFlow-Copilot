import json
from pathlib import Path
from PIL import Image, ImageDraw
import requests

API_URL = "http://127.0.0.1:8000/api/v1/generate-multimodal"
IMAGES_DIR = Path("tests/sample_images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = Path("docs/day2_test_results.json")


def create_wireframe(filename: str, title: str, lines: list[str]) -> Path:
    img = Image.new("RGB", (720, 440), color=(248, 250, 252))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 700, 75], fill=(30, 41, 59))
    draw.text((35, 38), title, fill=(255, 255, 255))
    y = 105
    for line in lines:
        draw.rectangle([35, y - 6, 680, y + 26], outline=(148, 163, 184), width=2)
        draw.text((48, y), line, fill=(15, 23, 42))
        y += 52
    path = IMAGES_DIR / filename
    img.save(path)
    return path


def build_sample_images() -> dict[str, Path]:
    return {
        "login": create_wireframe(
            "01_login_wireframe.png",
            "CLIENT PORTAL - SIGN IN",
            [
                "Input: Work Email Address",
                "Input: Password (masked)",
                "Checkbox: Remember me on this device",
                "Button [Primary]: Sign In",
                "Link: Forgot Password?",
            ],
        ),
        "checkout": create_wireframe(
            "02_checkout_wireframe.png",
            "ORDER SUMMARY & PAYMENT",
            [
                "Item: Pro Annual Plan - $120.00",
                "Input: Promo Code | Button: Apply",
                "Radio: Credit Card | Radio: Bank Transfer",
                "Button [Primary]: Confirm & Pay",
            ],
        ),
        "tickets": create_wireframe(
            "03_support_tickets.png",
            "HELPDESK TICKET QUEUE",
            [
                "Filter Dropdown: Status (Open, Pending, Resolved)",
                "Table Columns: Ticket ID | Customer | Priority | Updated",
                "Row 1: #1042 | Acme Corp | High | 10m ago",
                "Button: + New Ticket",
            ],
        ),
        "profile": create_wireframe(
            "04_user_profile.png",
            "ACCOUNT SETTINGS",
            [
                "Field: Full Name (Editable)",
                "Field: Role = 'Viewer' (Read-Only Badge)",
                "Toggle: Email Notifications [ON]",
                "Button [Danger]: Deactivate Account",
            ],
        ),
        "booking": create_wireframe(
            "05_room_booking.png",
            "MEETING ROOM SCHEDULER",
            [
                "Date Picker: 2026-11-20 | Floor: 3rd Floor",
                "Room A (Capacity: 8) - [Available] - Button: Book",
                "Room B (Capacity: 4) - [Booked 2pm-4pm]",
            ],
        ),
    }


def main():
    imgs = build_sample_images()

    text_cases = [
        ("T-01", "Text: Leave Management", "Employees submit annual or sick leave requests; managers approve or reject with comments.", None),
        ("T-02", "Text: Expense Tracker", "Staff upload receipt photos and enter expense amount and category for finance reimbursement.", None),
        ("T-03", "Text: Course Catalog", "Students browse available courses by semester, check prerequisites, and enroll online.", None),
        ("T-04", "Text: Vendor Directory", "Procurement team stores vendor contacts, tax IDs, and contract expiry dates.", None),
        ("T-05", "Text: Bug Triage Board", "QA logs bugs with severity and steps to reproduce; tech leads assign developers.", None),
    ]

    image_cases = [
        ("I-01", "Image-Only: Login Screen", "", imgs["login"]),
        ("I-02", "Image-Only: Checkout Screen", "", imgs["checkout"]),
        ("I-03", "Image-Only: Ticket Queue", "", imgs["tickets"]),
        ("I-04", "Image-Only: Account Settings", "", imgs["profile"]),
        ("I-05", "Image-Only: Room Scheduler", "", imgs["booking"]),
    ]

    combined_cases = [
        ("C-01", "Combined: Login + SSO Rule", "Support standard login shown in screenshot. Backend must lock accounts after 5 failed attempts; SSO is out of scope for v1.", imgs["login"]),
        ("C-02", "Combined: Checkout + Invoice Rule", "Implement the checkout UI shown. Generate a downloadable PDF receipt after payment confirmation.", imgs["checkout"]),
        ("C-03", "Combined: Helpdesk + SLA Alert", "Build the ticket queue view shown in wireframe. Escalate High priority tickets untouched for 2 hours.", imgs["tickets"]),
        ("C-04", "Combined: Profile + Audit Log", "Only Admins can change the Role field shown as read-only. Log all account deactivation events.", imgs["profile"]),
        ("C-05", "Combined: Scheduler + Recurring Rule", "Use the room booking layout shown. Prevent overlapping bookings and limit bookings to 2 hours max.", imgs["booking"]),
    ]

    all_cases = text_cases + image_cases + combined_cases
    results = []

    for case_id, name, text, img_path in all_cases:
        print(f"Running {case_id}: {name}...")
        files = None
        f_handle = None
        try:
            if img_path is not None:
                f_handle = open(img_path, "rb")
                files = {"image": (img_path.name, f_handle, "image/png")}

            resp = requests.post(
                API_URL,
                data={"project_name": name, "raw_text": text},
                files=files,
                timeout=300,
            )
            results.append(
                {
                    "case_id": case_id,
                    "project_name": name,
                    "status_code": resp.status_code,
                    "response": resp.json(),
                }
            )
            print(f"  -> HTTP {resp.status_code}")
        finally:
            if f_handle:
                f_handle.close()

    OUTPUT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved {len(results)} Day 2 results to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()