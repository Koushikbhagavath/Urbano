import os
import socket
import uuid
import time
SERVER_START_TIME = time.time()
import pymysql
import random
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from collections import deque

# pyrefly: ignore [missing-import]
from flask import Flask, request, jsonify, render_template, Response, send_from_directory
import queue
from deep_translator import GoogleTranslator

admin_sse_clients = []

def notify_admin(msg_dict):
    import json
    msg = json.dumps(msg_dict)
    dead = []
    for q in admin_sse_clients:
        try:
            q.put_nowait(msg)
        except queue.Full:
            dead.append(q)
    for q in dead:
        if q in admin_sse_clients:
            admin_sse_clients.remove(q)

# pyrefly: ignore [missing-import]
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)


SENDER_EMAIL = "urbanomaildelivery@gmail.com"
SENDER_PASSWORD = "ddpnycqajyoubitl"

import smtplib
import threading
from email.message import EmailMessage

def send_email_async_global(msg_obj):
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg_obj)
        server.quit()
    except Exception as e:
        print(f"FAILED TO SEND GLOBAL EMAIL ASYNC: {e}")

def send_status_update_email(cid, role_name="Urbano Support Team"):
    try:
        conn = get_db_connection()
        with conn.cursor() as c:
            c.execute("SELECT c.title, c.status, c.department_id, u.email, u.name FROM complaints c JOIN users u ON c.user_id = u.id WHERE c.id = %s", (cid,))
            row = c.fetchone()
            if role_name == 'Department' and row and row.get('department_id'):
                c.execute("SELECT name FROM departments WHERE id = %s", (row['department_id'],))
                dept_row = c.fetchone()
                if dept_row:
                    role_name = f"{dept_row['name']} Department"
        conn.close()
        if row and row.get('email'):
            msg = EmailMessage()
            msg["Subject"] = f"Update on Complaint #{cid}"
            msg["From"] = SENDER_EMAIL
            msg["To"] = row['email']
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                    <h2 style="color: #0d9488;">Urbano - Complaint Update</h2>
                    <p>Dear <strong>{row['name']}</strong>,</p>
                    <p>Your complaint <strong>#{cid} ('{row['title']}')</strong> has a new status update.</p>
                    <div style="background-color: #f3f4f6; padding: 15px; border-left: 4px solid #0d9488; margin: 20px 0; font-size: 16px;">
                        <strong>Current Status:</strong> {row['status']}
                    </div>
                    <p>Please check the Urbano app for more details.</p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
                    <p>Thank you,<br/><strong>By {role_name}</strong><br/>Urbano Support Team</p>
                </body>
            </html>
            """
            msg.set_content(f"Dear {row['name']},\n\nYour complaint #{cid} has a new status update.\n\nCurrent Status: {row['status']}\n\nPlease enable HTML to view this email.\n\nBy {role_name}")
            msg.add_alternative(html_content, subtype='html')
            threading.Thread(target=send_email_async_global, args=(msg,)).start()
    except Exception as e:
        print("Status email failed:", e)


# Trust one layer of reverse proxy headers (Cloudflare / Nginx)
# app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
import logging
class NoPingFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return not any(x in msg for x in [
            '/api/admin/system', 
            '/api/admin/sse', 
            '/api/admin/online_status',
            '/api/admin/managers',
            '/api/admin/departments',
            '/api/messages/threads',
            '/api/messages/fetch'
        ])
logging.getLogger('werkzeug').addFilter(NoPingFilter())


server_traffic_log = deque(maxlen=50)


@app.after_request
def log_response_info(response):
    # Only store major requests in UI log (ignore polling endpoints)
    ignore_paths = ['/api/admin/system', '/api/admin/sse', '/api/admin/online_status', '/api/messages/', '/api/admin/managers', '/api/admin/departments']
    if any(request.path.startswith(p) for p in ignore_paths):
        return response

    protocol = request.environ.get('SERVER_PROTOCOL', 'HTTP/1.1')
    log_entry = {
        "time": datetime.now().strftime("%d/%b/%Y %H:%M:%S"),
        "method": request.method,
        "path": request.path,
        "protocol": protocol,
        "status": response.status_code,
        "ip": request.remote_addr,
    }
    server_traffic_log.appendleft(log_entry)
    
    # Broadcast to SSE clients
    import json
    for q in admin_sse_clients:
        try:
            q.put(json.dumps({"type": "traffic", "log": log_entry}))
        except:
            pass
            
    return response


# Configuration
UPLOAD_FOLDER = "uploads/complaints/"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure the directory exists
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload limit

# Database configuration (Adjust these to match your local setup)
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "password"
DB_NAME = "clean_city"


def get_db_connection():
    try:
        return pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
        )
    except pymysql.MySQLError as db_err:
        raise RuntimeError(f"Database connection failed: {db_err}") from db_err


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "mp4", "mov", "avi"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/api/submit_complaint", methods=["POST"])
def submit_complaint():
    # 1. Extract text details from the form
    user_id = request.form.get("user_id")
    title = request.form.get("title")
    details = request.form.get("details")
    landmark = request.form.get("landmark")
    address = request.form.get("address")
    city = request.form.get("city")
    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")

    # Basic validation
    if not all([user_id, title, details, address, city]):
        return jsonify({"error": "Missing required text fields (including city)"}), 400

    # 2. Translate text to English for admin modules
    title_en = title
    details_en = details
    original_lang = "en"
    
    try:
        translator = GoogleTranslator(source='auto', target='en')
        title_en_trans = translator.translate(title)
        if title_en_trans: title_en = title_en_trans
        
        details_en_trans = translator.translate(details)
        if details_en_trans: details_en = details_en_trans
    except Exception as e:
        print(f"Translation failed: {e}")

    # 3. Database Operations with Transaction Management
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Action 1: Insert into complaints table
            insert_complaint_sql = """
                INSERT INTO complaints
                (user_id, title, details, landmark, address, city, latitude, longitude, status, title_en, details_en, original_lang)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Registered', %s, %s, %s)
            """
            cursor.execute(
                insert_complaint_sql,
                (user_id, title, details, landmark, address, city, latitude, longitude, title_en, details_en, original_lang),
            )

            # Retrieve the newly generated complaint_id
            complaint_id = cursor.lastrowid

            # Action 2: Extract and handle the media files
            media_paths = []
            if "files" in request.files or "file" in request.files:
                # Handle either a single file or a list of files
                files = request.files.getlist("files")
                if not files and "file" in request.files:
                    files = [request.files["file"]]

                for file in files:
                    if file and file.filename != "" and allowed_file(file.filename):
                        ext = file.filename.rsplit(".", 1)[1].lower()
                        media_type = (
                            "Video" if ext in {"mp4", "mov", "avi"} else "Image"
                        )

                        # Discard original filename — use a pure UUID to prevent path-traversal attacks
                        unique_filename = f"{uuid.uuid4().hex}.{ext}"
                        filepath = os.path.join(
                            app.config["UPLOAD_FOLDER"], unique_filename
                        )

                        # Save physical file — guard against disk-full / permission errors
                        try:
                            file.save(filepath)
                        except (IOError, OSError) as disk_err:
                            return jsonify({"success": False, "error": f"File storage error: {disk_err}"}), 500
                        media_paths.append(filepath)

                        # Insert the file path into complaint_media table
                        insert_media_sql = """
                            INSERT INTO complaint_media
                            (complaint_id, media_path, media_type)
                            VALUES (%s, %s, %s)
                        """
                        cursor.execute(
                            insert_media_sql, (complaint_id, filepath, media_type)
                        )

            # Action 3: Add to complaint_status_history for the vertical status
            # tracking!
            insert_history_sql = """
                INSERT INTO complaint_status_history
                (complaint_id, status, action_type, note, updated_by_role, updated_by_id)
                VALUES (%s, 'Registered', 'Initial Registration', 'New complaint, waiting for the team to solve', 'User', %s)
            """
            cursor.execute(insert_history_sql, (complaint_id, user_id))

        # Commit the transaction only if ALL inserts succeeded
        connection.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Complaint registered successfully",
                    "complaint_id": complaint_id,
                    "media_paths": media_paths,
                }
            ),
            201,
        )

    except Exception as e:
        connection.rollback()  # Undo DB changes if anything fails

        # Clean up the physical file if the database insert failed
        for path in media_paths:
            if os.path.exists(path):
                os.remove(path)

        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        connection.close()


@app.route("/api/register_user", methods=["POST"])
def register_user():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    email = data.get("email")
    mobile_number = data.get("mobile_number")
    password = data.get("password")
    name = data.get("name")
    age = data.get("age")
    gender = data.get("gender")
    address = data.get("address")

    # Basic validation for mandatory fields
    if not all([email, mobile_number, password, name, address]):
        return (
            jsonify(
                {
                    "error": "Missing required fields (email, mobile_number, password, name, address)"
                }
            ),
            400,
        )

    # Hash the password securely
    password_hash = generate_password_hash(password)

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check if email already exists
            check_sql = "SELECT id FROM users WHERE email = %s"
            cursor.execute(check_sql, (email,))
            if cursor.fetchone():
                return jsonify({"error": "Email already registered"}), 409

            # Insert new user
            insert_sql = """
                INSERT INTO users (email, mobile_number, password_hash, name, age, gender, address)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(
                insert_sql,
                (email, mobile_number, password_hash, name, age, gender, address),
            )

        connection.commit()
        return (
            jsonify({"success": True, "message": "User registered successfully"}),
            201,
        )

    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/login_user", methods=["POST"])
def login_user():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Fetch user from DB
            sql = "SELECT id, password_hash FROM users WHERE email = %s"
            cursor.execute(sql, (email,))
            user = cursor.fetchone()

            # Verify the hash matches the entered password
            if (
                user
                and user.get("password_hash")
                and check_password_hash(user["password_hash"], password)
            ):
                return (
                    jsonify(
                        {
                            "success": True,
                            "message": "Login successful",
                            "user_id": user["id"],
                        }
                    ),
                    200,
                )
            else:
                return jsonify({"error": "Invalid email or password"}), 401

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# --- MOBILE OTP ENDPOINTS ---


@app.route("/api/send_otp", methods=["POST"])
def send_otp():
    data = request.get_json()
    identifier = data.get("email")

    if not identifier:
        return (
            jsonify({"error": "Email, Manager ID, or Mobile Number is required"}),
            400,
        )
    identifier = identifier.strip()

    connection = get_db_connection()
    email = identifier
    try:
        with connection.cursor() as cursor:
            # Check if identifier matches a manager_id/mobile or department
            # dept_id
            cursor.execute(
                "SELECT email FROM managers WHERE manager_id = %s OR mobile_number = %s",
                (identifier, identifier),
            )
            manager = cursor.fetchone()
            if manager:
                email = manager["email"]
            else:
                cursor.execute(
                    "SELECT email FROM departments WHERE dept_id = %s", (identifier,)
                )
                dept = cursor.fetchone()
                if dept:
                    email = dept["email"]
                elif "@" not in identifier:
                    return (
                        jsonify({"error": "Invalid ID. No associated account found."}),
                        404,
                    )

            # Generate a 6-digit OTP
            import random
            from datetime import datetime, timedelta

            otp = str(random.randint(100000, 999999))
            expires_at = datetime.now() + timedelta(minutes=5)

            # Upsert the OTP (insert or update if email already exists in otps
            # table)
            sql = """
                INSERT INTO otps (email, otp, expires_at)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE otp = VALUES(otp), expires_at = VALUES(expires_at)
            """
            cursor.execute(sql, (email, otp, expires_at))
        connection.commit()

        # Actual Email Sending Logic via Gmail SMTP
        SENDER_EMAIL = "urbanomaildelivery@gmail.com"
        SENDER_PASSWORD = "ddpnycqajyoubitl"  # IMPORTANT: Replace this before testing!

        try:
            msg = EmailMessage()
            msg["Subject"] = "Your Urbano OTP Code"
            msg["From"] = SENDER_EMAIL
            msg["To"] = email
            
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; text-align: center; color: #333; padding: 40px; background-color: #f9fafb;">
                    <div style="max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        <h2 style="color: #0d9488; margin-top: 0;">Urbano Verification</h2>
                        <p style="font-size: 16px; margin-bottom: 20px;">Your One-Time Password (OTP) for verification is:</p>
                        <div style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #111; background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 0 auto 20px auto; width: fit-content;">
                            {otp}
                        </div>
                        <p style="color: #ef4444; font-size: 14px;"><strong>Note:</strong> This code expires in 5 minutes.</p>
                    </div>
                </body>
            </html>
            """
            msg.set_content(f"Your verification code is: {otp}\n\nIt expires in 5 minutes.")
            msg.add_alternative(html_content, subtype='html')

            import threading
            def send_email_async(msg_obj):
                try:
                    server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    server.send_message(msg_obj)
                    server.quit()
                except Exception as e:
                    print(f"FAILED TO SEND EMAIL ASYNC: {e}")

            threading.Thread(target=send_email_async, args=(msg,)).start()

            return (
                jsonify(
                    {"success": True, "message": "OTP sent successfully to your email!"}
                ),
                200,
            )

        except Exception as email_err:
            print(f"FAILED TO INITIATE EMAIL: {email_err}")
            print(f"FALLBACK CONSOLE OTP: {otp}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Failed to send email. Error: {str(email_err)}",
                    }
                ),
                500,
            )

    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/verify_otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    identifier = data.get("email")
    otp = data.get("otp")
    role = data.get("role", "User")  # Default to User if not provided

    if not identifier or not otp:
        return jsonify({"error": "Email/ID and OTP are required"}), 400

    connection = get_db_connection()
    email = identifier
    try:
        with connection.cursor() as cursor:
            # Check if identifier is a manager_id or mobile_number
            cursor.execute(
                "SELECT email FROM managers WHERE manager_id = %s OR mobile_number = %s",
                (identifier, identifier),
            )
            manager = cursor.fetchone()
            if manager:
                email = manager["email"]

            # 1. Verify OTP
            cursor.execute(
                "SELECT otp, expires_at FROM otps WHERE email = %s", (email,)
            )
            record = cursor.fetchone()

            if not record:
                return jsonify({"error": "No OTP found for this email"}), 404

            if record["otp"] != str(otp):
                return jsonify({"error": "Invalid OTP"}), 401

            if record["expires_at"] < datetime.now():
                return jsonify({"error": "OTP has expired"}), 401

            # OTP is valid! Delete it so it can't be reused
            cursor.execute("DELETE FROM otps WHERE email = %s", (email,))

            # 2. Check Role & Auto-Register if necessary
            if role == "User":
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()
                if user:
                    user_id = user["id"]
                    is_new = False
                else:
                    # Auto-register new user with unique temporary values to
                    # satisfy DB constraints
                    temp_mobile = f"OTP-{uuid.uuid4().hex[:8]}"
                    cursor.execute(
                        """
                        INSERT INTO users (email, mobile_number, name, password_hash)
                        VALUES (%s, %s, 'New Mobile User', '')
                    """,
                        (email, temp_mobile),
                    )
                    user_id = cursor.lastrowid
                    is_new = True

                connection.commit()
                return (
                    jsonify(
                        {
                            "success": True,
                            "message": "Login successful",
                            "user_id": user_id,
                            "role": "User",
                            "is_new": is_new,
                        }
                    ),
                    200,
                )

            elif role == "Manager":
                cursor.execute(
                    "SELECT id, is_approved, manager_id, name FROM managers WHERE email = %s",
                    (email,),
                )
                manager = cursor.fetchone()
                if manager:
                    manager_table_id = manager["id"]
                    is_approved = manager["is_approved"]
                    manager_id_str = manager["manager_id"]
                    is_new = (manager["name"] == 'Pending Manager')
                else:
                    # Auto-register pending manager
                    cursor.execute(
                        """
                        INSERT INTO managers (email, name, is_approved, password_hash)
                        VALUES (%s, 'Pending Manager', False, '')
                    """,
                        (email,),
                    )
                    manager_table_id = cursor.lastrowid
                    is_approved = False
                    manager_id_str = None
                    is_new = True

                # Mark manager as online on login
                try:
                    cursor.execute(
                        "UPDATE managers SET is_online=1, last_seen=NOW() WHERE id=%s",
                        (manager_table_id,)
                    )
                    notify_admin({"type": "status"})
                except Exception:
                    pass  # Column may not exist yet; handled gracefully

                connection.commit()
                return (
                    jsonify(
                        {
                            "success": True,
                            "message": "Login successful",
                            "manager_table_id": manager_table_id,
                            "manager_id": manager_id_str,
                            "is_approved": is_approved,
                            "role": "Manager",
                            "is_new": is_new,
                        }
                    ),
                    200,
                )

            elif role == "Department":
                cursor.execute(
                    "SELECT id, is_approved, dept_id, name FROM departments WHERE email = %s",
                    (email,),
                )
                dept = cursor.fetchone()
                if dept:
                    dept_table_id = dept["id"]
                    is_approved = dept["is_approved"]
                    dept_id_str = dept["dept_id"]
                    is_new = (dept["name"] == 'Pending Department')
                else:
                    # Auto-register pending department
                    cursor.execute(
                        """
                        INSERT INTO departments (email, name, is_approved, password_hash)
                        VALUES (%s, 'Pending Department', False, '')
                    """,
                        (email,),
                    )
                    dept_table_id = cursor.lastrowid
                    is_approved = False
                    dept_id_str = None
                    is_new = True

                # Mark department as online on login
                try:
                    cursor.execute(
                        "UPDATE departments SET is_online=1, last_seen=NOW() WHERE id=%s",
                        (dept_table_id,)
                    )
                    notify_admin({"type": "status"})
                except Exception:
                    pass  # Column may not exist yet; handled gracefully

                connection.commit()
                return (
                    jsonify(
                        {
                            "success": True,
                            "message": "Login successful",
                            "department_table_id": dept_table_id,
                            "dept_id": dept_id_str,
                            "is_approved": is_approved,
                            "role": "Department",
                            "is_new": is_new,
                        }
                    ),
                    200,
                )

            elif role == "Admin":
                cursor.execute("SELECT id FROM admins WHERE email = %s", (email,))
                admin = cursor.fetchone()
                if admin:
                    admin_id = admin["id"]
                    connection.commit()
                    return (
                        jsonify(
                            {
                                "success": True,
                                "message": "Login successful",
                                "admin_id": admin_id,
                                "role": "Admin",
                            }
                        ),
                        200,
                    )
                else:
                    return jsonify({"error": "Unauthorized Admin email"}), 403

            else:
                return jsonify({"error": "Invalid role"}), 400

    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# --- MOBILE APP USER API ---


@app.route("/api/user/profile", methods=["GET"])
def get_user_profile():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, email, mobile_number, age, gender, address FROM users WHERE id = %s",
                (user_id,),
            )
            user = cursor.fetchone()
            if not user:
                return jsonify({"error": "User not found"}), 404

            return jsonify({"success": True, "profile": user}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/user/update_profile", methods=["POST"])
def update_user_profile():
    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    name = data.get("name")
    mobile_number = data.get("mobile_number")
    age = data.get("age")
    gender = data.get("gender")
    address = data.get("address")

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # We explicitly DO NOT update email here.
            sql = """
                UPDATE users
                SET name = %s, mobile_number = %s, age = %s, gender = %s, address = %s
                WHERE id = %s
            """
            cursor.execute(sql, (name, mobile_number, age, gender, address, user_id))
        connection.commit()
        return (
            jsonify({"success": True, "message": "Profile updated successfully"}),
            200,
        )
    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/user/request_email_change", methods=["POST"])
def request_email_change():
    data = request.get_json()
    new_email = data.get("new_email")

    if not new_email:
        return jsonify({"error": "New email is required"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check if email is already used by someone else
            cursor.execute("SELECT id FROM users WHERE email = %s", (new_email,))
            if cursor.fetchone():
                return jsonify({"error": "Email already exists"}), 409

        # Generate a 6-digit OTP
        import random
        from datetime import datetime, timedelta

        otp = str(random.randint(100000, 999999))
        expires_at = datetime.now() + timedelta(minutes=5)

        with connection.cursor() as cursor:
            # Upsert the OTP
            sql = """
                INSERT INTO otps (email, otp, expires_at)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE otp = VALUES(otp), expires_at = VALUES(expires_at)
            """
            cursor.execute(sql, (new_email, otp, expires_at))
        connection.commit()

        # Email Sending Logic
        SENDER_EMAIL = "urbanomaildelivery@gmail.com"
        SENDER_PASSWORD = "ddpnycqajyoubitl"
        import smtplib
        from email.message import EmailMessage

        try:
            msg = EmailMessage()
            msg.set_content(
                f"Your email verification code is: {otp}\n\nIt expires in 5 minutes."
            )
            msg["Subject"] = "Your Urbano Email Change OTP"
            msg["From"] = SENDER_EMAIL
            msg["To"] = new_email

            server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
            server.quit()

            return (
                jsonify(
                    {
                        "success": True,
                        "message": "OTP sent successfully to your new email!",
                    }
                ),
                200,
            )

        except smtplib.SMTPException as smtp_err:
            print(f"SMTP error sending email change OTP: {smtp_err}")
            return jsonify({"success": False, "error": "Email service error. Please try again later."}), 503
        except socket.timeout:
            print("SMTP connection timed out while sending email change OTP.")
            return jsonify({"success": False, "error": "Email service timed out. Please try again later."}), 503
        except Exception as email_err:
            print(f"FAILED TO SEND EMAIL: {email_err}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Failed to send email. Error: {str(email_err)}",
                    }
                ),
                500,
            )

    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/user/verify_email_change", methods=["POST"])
def verify_email_change():
    from datetime import datetime

    data = request.get_json()
    user_id = data.get("user_id")
    new_email = data.get("new_email")
    otp = data.get("otp")

    if not all([user_id, new_email, otp]):
        return jsonify({"error": "Missing required fields"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Verify OTP
            cursor.execute(
                "SELECT otp, expires_at FROM otps WHERE email = %s", (new_email,)
            )
            record = cursor.fetchone()

            if not record:
                return jsonify({"error": "No OTP found for this email"}), 404

            if record["otp"] != str(otp):
                return jsonify({"error": "Invalid OTP"}), 401

            if record["expires_at"] < datetime.now():
                return jsonify({"error": "OTP has expired"}), 401

            # Update email in users table
            cursor.execute(
                "UPDATE users SET email = %s WHERE id = %s", (new_email, user_id)
            )

            # Delete OTP
            cursor.execute("DELETE FROM otps WHERE email = %s", (new_email,))

        connection.commit()
        return jsonify({"success": True, "message": "Email updated successfully"}), 200

    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/user/complaints", methods=["GET"])
def get_user_complaints():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Fetch complaints (Recent first)
            cursor.execute(
                """
                SELECT c.id, c.title, c.details, c.title_en, c.details_en, c.original_lang, c.landmark, c.address, c.city, c.status, c.created_at, c.latitude, c.longitude,
                       d.name as department_name, m.name as manager_name
                FROM complaints c
                LEFT JOIN departments d ON c.department_id = d.id
                LEFT JOIN managers m ON c.assigned_by_manager_id = m.id
                WHERE c.user_id = %s 
                ORDER BY c.created_at DESC
                """,
                (user_id,),
            )
            complaints = cursor.fetchall()

            # Attach media and history to each complaint
            for c in complaints:
                # Get media
                cursor.execute(
                    "SELECT media_path FROM complaint_media WHERE complaint_id = %s",
                    (c["id"],),
                )
                c["media"] = [m["media_path"] for m in cursor.fetchall()]

                # Get history
                cursor.execute(
                    "SELECT status, action_type, note, expected_resolution_date, created_at, updated_by_role FROM complaint_status_history WHERE complaint_id = %s ORDER BY created_at ASC",
                    (c["id"],),
                )
                c["history"] = cursor.fetchall()

            return jsonify({"success": True, "complaints": complaints}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# --- MANAGER ENDPOINTS ---


@app.route("/api/manager/profile", methods=["GET"])
def get_manager_profile():
    manager_table_id = request.args.get("manager_table_id")
    if not manager_table_id:
        return jsonify({"error": "manager_table_id is required"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, manager_id, email, name, mobile_number, age, gender, dob, address, assigned_city, is_approved FROM managers WHERE id = %s",
                (manager_table_id,),
            )
            manager = cursor.fetchone()
            if not manager:
                return jsonify({"error": "Manager not found"}), 404

            # format date if needed
            if manager["dob"]:
                manager["dob"] = manager["dob"].strftime("%Y-%m-%d")

            return jsonify({"success": True, "profile": manager}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/manager/update_profile", methods=["POST"])
def update_manager_profile():
    data = request.get_json()
    manager_table_id = data.get("manager_table_id")
    name = data.get("name")
    mobile_number = data.get("mobile_number")
    age = data.get("age")
    gender = data.get("gender")
    dob = data.get("dob")
    address = data.get("address")

    if not manager_table_id or not name or not mobile_number:
        return (
            jsonify(
                {"error": "Missing fields (manager_table_id, name, mobile_number)"}
            ),
            400,
        )

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = "UPDATE managers SET name = %s, mobile_number = %s, age = %s, gender = %s, dob = %s, address = %s WHERE id = %s"
            cursor.execute(
                sql, (name, mobile_number, age, gender, dob, address, manager_table_id)
            )
        connection.commit()
        return (
            jsonify(
                {"success": True, "message": "Manager profile updated successfully"}
            ),
            200,
        )
    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# --- DEPARTMENT ENDPOINTS ---


@app.route("/api/department/profile", methods=["GET"])
def get_department_profile():
    dept_table_id = request.args.get("dept_table_id")
    if not dept_table_id:
        return jsonify({"error": "dept_table_id is required"}), 400
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, dept_id, name, email, head_name, contact_number,
                       number_of_employees, address, assigned_city, is_approved,
                       operating_hours, emergency_contact
                FROM departments WHERE id = %s
            """,
                (dept_table_id,),
            )
            dept = cursor.fetchone()
            if not dept:
                return jsonify({"error": "Department not found"}), 404
            return jsonify({"success": True, "profile": dept}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/department/update_profile", methods=["POST"])
def update_department_profile():
    data = request.get_json()
    dept_table_id = data.get("dept_table_id")
    if not dept_table_id:
        return jsonify({"error": "dept_table_id is required"}), 400
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # First fetch the existing name if name isn't provided, or just
            # update if it is
            new_name = data.get("name")

            if new_name:
                cursor.execute(
                    """
                    UPDATE departments
                    SET name = %s, head_name = %s, contact_number = %s, address = %s,
                        number_of_employees = %s, assigned_city = %s, operating_hours = %s, emergency_contact = %s
                    WHERE id = %s
                """,
                    (
                        new_name,
                        data.get("head_name"),
                        data.get("contact_number"),
                        data.get("address"),
                        data.get("number_of_employees"),
                        data.get("assigned_city"),
                        data.get("operating_hours"),
                        data.get("emergency_contact"),
                        dept_table_id,
                    ),
                )
            else:
                cursor.execute(
                    """
                    UPDATE departments
                    SET head_name = %s, contact_number = %s, address = %s,
                        number_of_employees = %s, operating_hours = %s, emergency_contact = %s
                    WHERE id = %s
                """,
                    (
                        data.get("head_name"),
                        data.get("contact_number"),
                        data.get("address"),
                        data.get("number_of_employees"),
                        data.get("operating_hours"),
                        data.get("emergency_contact"),
                        dept_table_id,
                    ),
                )
        connection.commit()
        return jsonify({"success": True, "message": "Department profile updated"}), 200
    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/department/update_email", methods=["POST"])
def update_department_email():
    data = request.get_json()
    dept_table_id = data.get("dept_table_id")
    new_email = data.get("new_email", "").strip()
    otp = str(data.get("otp", ""))
    if not dept_table_id or not new_email or not otp:
        return jsonify({"error": "dept_table_id, new_email and otp are required"}), 400
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Verify OTP against new email
            cursor.execute(
                "SELECT otp, expires_at FROM otps WHERE email = %s", (new_email,)
            )
            record = cursor.fetchone()
            if not record:
                return (
                    jsonify(
                        {
                            "error": "No OTP found for this email. Please request a new OTP."
                        }
                    ),
                    404,
                )
            if record["otp"] != otp:
                return jsonify({"error": "Incorrect OTP. Please try again."}), 401
            if record["expires_at"] < datetime.now():
                return (
                    jsonify({"error": "OTP has expired. Please request a new one."}),
                    401,
                )
            # OTP valid — delete it
            cursor.execute("DELETE FROM otps WHERE email = %s", (new_email,))
            # Check email not already used
            cursor.execute(
                "SELECT id FROM departments WHERE email = %s AND id != %s",
                (new_email, dept_table_id),
            )
            if cursor.fetchone():
                return (
                    jsonify(
                        {"error": "This email is already in use by another department."}
                    ),
                    409,
                )
            # Update
            cursor.execute(
                "UPDATE departments SET email = %s WHERE id = %s",
                (new_email, dept_table_id),
            )
        connection.commit()
        return jsonify({"success": True, "message": "Email updated successfully"}), 200
    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# --- ADMIN ENDPOINTS ---


@app.route("/api/admin/approve_manager", methods=["POST"])
def approve_manager():
    data = request.get_json()
    manager_table_id = data.get("manager_table_id")  # The auto-increment ID
    assigned_city = data.get("assigned_city")

    if not manager_table_id or not assigned_city:
        return (
            jsonify({"error": "manager_table_id and assigned_city are required"}),
            400,
        )

    # Generate a unique Manager ID like "MGR-XYZ123"
    generated_manager_id = f"MGR-{uuid.uuid4().hex[:6].upper()}"

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            update_sql = "UPDATE managers SET is_approved = TRUE, assigned_city = %s, manager_id = %s WHERE id = %s"
            cursor.execute(
                update_sql, (assigned_city, generated_manager_id, manager_table_id)
            )
            if cursor.rowcount == 0:
                return jsonify({"error": "Manager not found"}), 404
        connection.commit()
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Manager approved and city assigned",
                    "manager_id": generated_manager_id,
                }
            ),
            200,
        )
    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/admin/approve_department", methods=["POST"])
def approve_department():
    data = request.get_json()
    dept_table_id = data.get("dept_table_id")

    if not dept_table_id:
        return jsonify({"error": "dept_table_id is required"}), 400

    generated_dept_id = f"DEPT-{uuid.uuid4().hex[:6].upper()}"

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            update_sql = (
                "UPDATE departments SET is_approved = TRUE, dept_id = %s WHERE id = %s"
            )
            cursor.execute(update_sql, (generated_dept_id, dept_table_id))
            if cursor.rowcount == 0:
                return jsonify({"error": "Department not found"}), 404
        connection.commit()
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Department approved",
                    "dept_id": generated_dept_id,
                }
            ),
            200,
        )
    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# --- MANAGER WORKFLOW ENDPOINTS ---


@app.route("/api/manager/complaint_media", methods=["GET"])
def get_complaint_media():
    complaint_id = request.args.get("complaint_id")
    if not complaint_id:
        return jsonify({"error": "complaint_id is required"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT media_path, media_type FROM complaint_media WHERE complaint_id = %s",
                (complaint_id,),
            )
            media = cursor.fetchall()
        return (
            jsonify({"success": True, "media": [m["media_path"] for m in media]}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/manager/pending_complaints", methods=["GET"])
def get_pending_complaints():
    manager_table_id = request.args.get("manager_table_id")

    if not manager_table_id:
        return jsonify({"error": "manager_table_id is required"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Verify manager is approved and get assigned city
            cursor.execute(
                "SELECT is_approved, assigned_city FROM managers WHERE id = %s",
                (manager_table_id,),
            )
            manager = cursor.fetchone()

            if not manager:
                return jsonify({"error": "Manager not found"}), 404
            if not manager["is_approved"]:
                return jsonify({"error": "Manager is not approved"}), 403

            assigned_city = manager["assigned_city"]
            if not assigned_city:
                return jsonify({"error": "No city assigned to this manager yet"}), 400

            # Fetch complaints for this city joined with users table
            sql = """
                SELECT c.id, c.title, c.details, c.title_en, c.details_en, c.original_lang, c.address, c.landmark, c.city, c.latitude, c.longitude, c.status, c.created_at,
                       u.name as user_name, u.email as user_email, u.mobile_number as user_mobile, u.address as user_address
                FROM complaints c
                JOIN users u ON c.user_id = u.id
                WHERE c.status = 'Registered' AND c.city = %s
                ORDER BY c.created_at DESC
            """
            cursor.execute(sql, (assigned_city,))
            complaints = cursor.fetchall()
            # Serialize datetimes
            for c in complaints:
                if c.get("created_at"):
                    c["created_at"] = c["created_at"].strftime("%Y-%m-%d %H:%M:%S")

            return jsonify({"success": True, "complaints": complaints}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/manager/all_assigned_complaints", methods=["GET"])
def get_all_assigned_complaints():
    manager_table_id = request.args.get("manager_table_id")

    if not manager_table_id:
        return jsonify({"error": "manager_table_id is required"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Verify manager is approved and get assigned city
            cursor.execute(
                "SELECT is_approved, assigned_city FROM managers WHERE id = %s",
                (manager_table_id,),
            )
            manager = cursor.fetchone()

            if (
                not manager
                or not manager["is_approved"]
                or not manager["assigned_city"]
            ):
                return (
                    jsonify(
                        {
                            "error": "Manager not found, not approved, or no assigned city"
                        }
                    ),
                    403,
                )

            assigned_city = manager["assigned_city"]

            # Fetch complaints (status != 'Registered') for this city,
            # including full user info and assignment date
            sql = """
                SELECT c.id, c.title, c.details, c.title_en, c.details_en, c.original_lang, c.address, c.landmark, c.city,
                       c.latitude, c.longitude, c.status, c.created_at,
                       d.name as department_name, d.id as department_id,
                       d.contact_number as dept_contact,
                       u.name as user_name, u.email as user_email,
                       u.mobile_number as user_mobile, u.address as user_address,
                       (SELECT csh.created_at FROM complaint_status_history csh
                        WHERE csh.complaint_id = c.id AND csh.action_type = 'Assigned to Dept'
                        ORDER BY csh.created_at DESC LIMIT 1) as assigned_at
                FROM complaints c
                JOIN departments d ON c.department_id = d.id
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.status NOT IN ('Registered', 'Return Pending') AND c.city = %s
                ORDER BY d.name, c.created_at DESC
            """
            cursor.execute(sql, (assigned_city,))
            complaints = cursor.fetchall()
            for c in complaints:
                if c.get("created_at"):
                    c["created_at"] = c["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                if c.get("assigned_at"):
                    c["assigned_at"] = c["assigned_at"].strftime("%Y-%m-%d %H:%M:%S")

            return jsonify({"success": True, "complaints": complaints}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/manager/departments", methods=["GET"])
def get_manager_departments():
    manager_table_id = request.args.get("manager_table_id")

    if not manager_table_id:
        return jsonify({"error": "manager_table_id is required"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Get manager's city
            cursor.execute(
                "SELECT is_approved, assigned_city FROM managers WHERE id = %s",
                (manager_table_id,),
            )
            manager = cursor.fetchone()

            if not manager or not manager["is_approved"]:
                return jsonify({"error": "Manager not found or not approved"}), 403

            manager_city = manager["assigned_city"]

            # Fetch approved departments in that exact city
            cursor.execute(
                "SELECT id, dept_id, name FROM departments WHERE assigned_city = %s AND is_approved = TRUE",
                (manager_city,),
            )
            departments = cursor.fetchall()

            return jsonify({"success": True, "departments": departments}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/manager/assign_complaint", methods=["POST"])
def assign_complaint():
    data = request.get_json()
    manager_table_id = data.get("manager_table_id")
    complaint_id = data.get("complaint_id")
    # The auto-increment table ID of the department
    department_id = data.get("department_id")
    note = data.get("note")

    if not all([manager_table_id, complaint_id, department_id, note]):
        return jsonify({"error": "Missing required fields"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 1. Verify manager is approved
            cursor.execute(
                "SELECT is_approved, assigned_city FROM managers WHERE id = %s",
                (manager_table_id,),
            )
            manager = cursor.fetchone()
            if not manager or not manager["is_approved"]:
                return jsonify({"error": "Manager not found or not approved"}), 403
            manager_city = manager["assigned_city"]

            # 2. Get department name and enforce Geo-Fence matching
            cursor.execute(
                "SELECT name, assigned_city FROM departments WHERE id = %s",
                (department_id,),
            )
            dept = cursor.fetchone()
            if not dept:
                return jsonify({"error": "Department not found"}), 404
            if dept["assigned_city"] != manager_city:
                return (
                    jsonify(
                        {
                            "error": "Cross-city assignment forbidden. This department is not in your city."
                        }
                    ),
                    403,
                )

            dynamic_status = f"Task Assigned to {dept['name']}"

            # 3. Action 1: Update complaints table
            update_sql = """
                UPDATE complaints
                SET department_id = %s, assigned_by_manager_id = %s, status = %s
                WHERE id = %s
            """
            cursor.execute(
                update_sql,
                (department_id, manager_table_id, dynamic_status, complaint_id),
            )

            if cursor.rowcount == 0:
                # If no rows updated, complaint might not exist
                connection.rollback()
                return jsonify({"error": "Complaint not found"}), 404

            # 4. Action 2: Insert into history
            insert_history_sql = """
                INSERT INTO complaint_status_history
                (complaint_id, status, action_type, note, updated_by_role, updated_by_id)
                VALUES (%s, %s, 'Assigned to Dept', %s, 'Manager', %s)
            """
            cursor.execute(
                insert_history_sql,
                (complaint_id, "Task Assigned", note, manager_table_id),
            )

        # Commit transaction
        connection.commit()
        send_status_update_email(complaint_id, "Manager")
        return (
            jsonify({"success": True, "message": "Complaint successfully assigned."}),
            200,
        )

    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# --- DEPARTMENT WORKFLOW ENDPOINTS ---


@app.route("/api/department/complaints", methods=["GET"])
def get_department_complaints():
    dept_table_id = request.args.get("dept_table_id")
    # active | resolved | return_pending
    status_filter = request.args.get("filter", "active")
    if not dept_table_id:
        return jsonify({"error": "dept_table_id is required"}), 400
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT is_approved, assigned_city FROM departments WHERE id = %s",
                (dept_table_id,),
            )
            dept = cursor.fetchone()
            if not dept:
                return jsonify({"error": "Department not found"}), 404
            if not dept["is_approved"]:
                return jsonify({"error": "Department is not approved"}), 403

            if status_filter == "active":
                status_clause = "c.status LIKE 'Task Assigned%%'"
            elif status_filter == "working":
                status_clause = "c.status = 'Working'"
            elif status_filter == "resolved":
                status_clause = "c.status = 'Resolved'"
            elif status_filter == "all":
                status_clause = "1=1"
            else:  # return_pending
                status_clause = "c.status = 'Return Pending'"

            sql = f"""
                SELECT c.id, c.title, c.details, c.title_en, c.details_en, c.original_lang, c.address, c.landmark, c.city,
                       c.latitude, c.longitude, c.status, c.created_at,
                       u.name as user_name, u.email as user_email,
                       u.mobile_number as user_mobile, u.address as user_address,
                       (SELECT csh.created_at FROM complaint_status_history csh
                        WHERE csh.complaint_id = c.id AND csh.action_type = 'Assigned to Dept'
                        ORDER BY csh.created_at DESC LIMIT 1) as assigned_at
                FROM complaints c
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.department_id = %s AND {status_clause}
                ORDER BY c.created_at DESC
            """
            cursor.execute(sql, (dept_table_id,))
            complaints = cursor.fetchall()
            for c in complaints:
                for field in ["created_at", "assigned_at"]:
                    if c.get(field):
                        c[field] = c[field].strftime("%Y-%m-%d %H:%M:%S")

            # Also return summary counts
            cursor.execute(
                """
                SELECT
                  SUM(CASE WHEN status LIKE 'Task Assigned%%' THEN 1 ELSE 0 END) as active,
                  SUM(CASE WHEN status = 'Working' THEN 1 ELSE 0 END) as working,
                  SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved,
                  SUM(CASE WHEN status = 'Return Pending' THEN 1 ELSE 0 END) as return_pending,
                  COUNT(*) as all_complaints
                FROM complaints WHERE department_id = %s
            """,
                (dept_table_id,),
            )
            counts = cursor.fetchone()

            return (
                jsonify({"success": True, "complaints": complaints, "counts": counts}),
                200,
            )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# Keep old endpoint alias for backward compatibility
@app.route("/api/department/assigned_complaints", methods=["GET"])
def get_assigned_complaints():
    return get_department_complaints()


@app.route("/api/department/action", methods=["POST"])
def department_action():
    """Handles all department actions: Dispatch, Delay, Resolve, Return"""
    data = request.get_json()
    dept_table_id = data.get("dept_table_id")
    complaint_id = data.get("complaint_id")
    # Dispatch | Delay | Resolve | Return
    action_type = data.get("action_type")
    note = data.get("note", "")
    expected_resolution_date = data.get("expected_resolution_date")

    if not all([dept_table_id, complaint_id, action_type]):
        return jsonify({"error": "Missing required fields"}), 400
    if action_type in ["Dispatch", "Delay", "Return"] and not note:
        return jsonify({"error": f"A note/reason is required for {action_type}"}), 400
    if action_type == "Delay" and not expected_resolution_date:
        return jsonify({"error": "expected_resolution_date is required for Delay"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT is_approved FROM departments WHERE id = %s", (dept_table_id,)
            )
            dept = cursor.fetchone()
            if not dept or not dept["is_approved"]:
                return jsonify({"error": "Department not found or not approved"}), 403

            # Verify complaint belongs to this dept
            cursor.execute(
                """
                SELECT c.id, u.email as user_email, u.name as user_name, c.title,
                       c.created_at, c.details, c.title_en, c.details_en, c.original_lang, c.address
                FROM complaints c
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.id = %s AND c.department_id = %s
            """,
                (complaint_id, dept_table_id),
            )
            complaint = cursor.fetchone()
            if not complaint:
                return (
                    jsonify(
                        {
                            "error": "Complaint not found or not assigned to this department"
                        }
                    ),
                    404,
                )

            if action_type == "Dispatch":
                new_status = "Working"
                hist_action = "Team Dispatched"
                cursor.execute(
                    "UPDATE complaints SET status = %s WHERE id = %s",
                    (new_status, complaint_id),
                )
                cursor.execute(
                    """
                    INSERT INTO complaint_status_history
                    (complaint_id, status, action_type, note, updated_by_role, updated_by_id)
                    VALUES (%s, %s, %s, %s, 'Department', %s)
                """,
                    (complaint_id, new_status, hist_action, note, dept_table_id),
                )

            elif action_type == "Delay":
                new_status = "Working"
                hist_action = "Delayed"
                cursor.execute(
                    "UPDATE complaints SET status = %s WHERE id = %s",
                    (new_status, complaint_id),
                )
                cursor.execute(
                    """
                    INSERT INTO complaint_status_history
                    (complaint_id, status, action_type, note, expected_resolution_date, updated_by_role, updated_by_id)
                    VALUES (%s, %s, %s, %s, %s, 'Department', %s)
                """,
                    (
                        complaint_id,
                        new_status,
                        hist_action,
                        note,
                        expected_resolution_date,
                        dept_table_id,
                    ),
                )

            elif action_type == "Resolve":
                new_status = "Resolved"
                hist_action = "Resolved"
                cursor.execute(
                    "UPDATE complaints SET status = %s WHERE id = %s",
                    (new_status, complaint_id),
                )
                cursor.execute(
                    """
                    INSERT INTO complaint_status_history
                    (complaint_id, status, action_type, note, updated_by_role, updated_by_id)
                    VALUES (%s, 'Resolved', 'Resolved', 'Complaint resolved by department.', 'Department', %s)
                """,
                    (complaint_id, dept_table_id),
                )
                connection.commit()
                send_status_update_email(complaint_id, "Department")
                return (
                    jsonify(
                        {
                            "success": True,
                            "message": "Complaint resolved and user notified.",
                        }
                    ),
                    200,
                )

            elif action_type == "Return":
                new_status = "Return Pending"
                hist_action = "Return Requested"
                cursor.execute(
                    "UPDATE complaints SET status = %s WHERE id = %s",
                    (new_status, complaint_id),
                )
                cursor.execute(
                    """
                    INSERT INTO complaint_status_history
                    (complaint_id, status, action_type, note, updated_by_role, updated_by_id)
                    VALUES (%s, %s, %s, %s, 'Department', %s)
                """,
                    (complaint_id, new_status, hist_action, note, dept_table_id),
                )
            else:
                return jsonify({"error": "Invalid action_type"}), 400

        connection.commit()
        send_status_update_email(complaint_id, "Department")
        return (
            jsonify({"success": True, "message": f"Action {action_type} completed."}),
            200,
        )
    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# Keep backward-compatible alias
@app.route("/api/department/update_status", methods=["POST"])
def update_status():
    data = request.get_json()
    if data:
        data["action_type"] = data.get("update_type")
        data["note"] = data.get("manual_note")
    return department_action()


@app.route("/uploads/complaints/<path:filename>")
def serve_uploads(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# --- SHARED: COMPLAINT HISTORY ---


@app.route("/api/complaint_history", methods=["GET"])
def get_complaint_history():
    complaint_id = request.args.get("complaint_id")
    if not complaint_id:
        return jsonify({"error": "complaint_id is required"}), 400
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT action_type, status, note, expected_resolution_date, updated_by_role, created_at
                FROM complaint_status_history
                WHERE complaint_id = %s ORDER BY created_at ASC
            """,
                (complaint_id,),
            )
            history = cursor.fetchall()
            for h in history:
                if h.get("created_at"):
                    h["created_at"] = h["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                if h.get("expected_resolution_date"):
                    h["expected_resolution_date"] = str(h["expected_resolution_date"])
            return jsonify({"success": True, "history": history}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# --- WEB DASHBOARD PAGE ROUTES ---


@app.route("/")
@app.route("/portal")
def serve_portal():
    return render_template("portal.html")


@app.route("/manager/login")
@app.route("/login")  # backward compat
def serve_manager_login():
    return render_template("login.html")


@app.route("/manager")
def serve_manager():
    return render_template("manager.html")


@app.route("/department/login")
def serve_department_login():
    return render_template("department_login.html")


@app.route("/department")
def serve_department():
    return render_template("department.html")


# --- MANAGER EMAIL CHANGE OTP ---


@app.route("/api/manager/request_email_change", methods=["POST"])
def manager_request_email_change():
    data = request.get_json()
    new_email = data.get("new_email")
    manager_table_id = data.get("manager_table_id")

    if not new_email or not manager_table_id:
        return jsonify({"error": "new_email and manager_table_id are required"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check if email is already in use
            cursor.execute(
                "SELECT id FROM managers WHERE email = %s AND id != %s",
                (new_email, manager_table_id),
            )
            if cursor.fetchone():
                return (
                    jsonify({"error": "Email already in use by another manager"}),
                    409,
                )

        otp = str(random.randint(100000, 999999))
        expires_at = datetime.now() + timedelta(minutes=5)

        with connection.cursor() as cursor:
            sql = """
                INSERT INTO otps (email, otp, expires_at)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE otp = VALUES(otp), expires_at = VALUES(expires_at)
            """
            cursor.execute(sql, (new_email, otp, expires_at))
        connection.commit()

        SENDER_EMAIL = "urbanomaildelivery@gmail.com"
        SENDER_PASSWORD = "ddpnycqajyoubitl"
        try:
            msg = EmailMessage()
            msg.set_content(
                f"Your Urbano email change verification code is: {otp}\n\nIt expires in 5 minutes."
            )
            msg["Subject"] = "Your Urbano Email Change OTP"
            msg["From"] = SENDER_EMAIL
            msg["To"] = new_email
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
            server.quit()
            return jsonify({"success": True, "message": "OTP sent to new email"}), 200
        except smtplib.SMTPException as smtp_err:
            print(f"SMTP error sending manager email change OTP: {smtp_err}")
            return jsonify({"success": False, "error": "Email service error. Please try again later."}), 503
        except socket.timeout:
            print("SMTP connection timed out while sending manager email change OTP.")
            return jsonify({"success": False, "error": "Email service timed out. Please try again later."}), 503
        except Exception as email_err:
            print(f"FAILED TO SEND EMAIL: {email_err}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Failed to send email: {str(email_err)}",
                    }
                ),
                500,
            )

    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/manager/verify_email_change", methods=["POST"])
def manager_verify_email_change():
    data = request.get_json()
    manager_table_id = data.get("manager_table_id")
    new_email = data.get("new_email")
    otp = data.get("otp")

    if not all([manager_table_id, new_email, otp]):
        return jsonify({"error": "Missing required fields"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT otp, expires_at FROM otps WHERE email = %s", (new_email,)
            )
            record = cursor.fetchone()

            if not record:
                return jsonify({"error": "No OTP found for this email"}), 404
            if record["otp"] != str(otp):
                return jsonify({"error": "Invalid OTP"}), 401
            if record["expires_at"] < datetime.now():
                return jsonify({"error": "OTP has expired"}), 401

            cursor.execute(
                "UPDATE managers SET email = %s WHERE id = %s",
                (new_email, manager_table_id),
            )
            cursor.execute("DELETE FROM otps WHERE email = %s", (new_email,))

        connection.commit()
        return jsonify({"success": True, "message": "Email updated successfully"}), 200

    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# --- MANAGER RETURN REQUEST ENDPOINTS ---


@app.route("/api/manager/return_requests", methods=["GET"])
def get_return_requests():
    """Fetch complaints with status = Return Pending for manager's city."""
    manager_table_id = request.args.get("manager_table_id")
    if not manager_table_id:
        return jsonify({"error": "manager_table_id is required"}), 400
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT is_approved, assigned_city FROM managers WHERE id = %s",
                (manager_table_id,),
            )
            manager = cursor.fetchone()
            if (
                not manager
                or not manager["is_approved"]
                or not manager["assigned_city"]
            ):
                return (
                    jsonify(
                        {
                            "error": "Manager not found, not approved, or no city assigned"
                        }
                    ),
                    403,
                )
            cursor.execute(
                """
                SELECT c.id, c.title, c.details, c.title_en, c.details_en, c.original_lang, c.address, c.landmark, c.city, c.status, c.created_at,
                       d.name as department_name, d.id as department_id,
                       u.name as user_name, u.email as user_email,
                       u.mobile_number as user_mobile,
                       (SELECT csh.note FROM complaint_status_history csh
                        WHERE csh.complaint_id = c.id AND csh.action_type = 'Return Requested'
                        ORDER BY csh.created_at DESC LIMIT 1) as return_reason,
                       (SELECT csh.created_at FROM complaint_status_history csh
                        WHERE csh.complaint_id = c.id AND csh.action_type = 'Return Requested'
                        ORDER BY csh.created_at DESC LIMIT 1) as returned_at
                FROM complaints c
                JOIN departments d ON c.department_id = d.id
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.status = 'Return Pending' AND c.city = %s
                ORDER BY c.created_at DESC
            """,
                (manager["assigned_city"],),
            )
            complaints = cursor.fetchall()
            for c in complaints:
                for f in ["created_at", "returned_at"]:
                    if c.get(f):
                        c[f] = c[f].strftime("%Y-%m-%d %H:%M:%S")
            return jsonify({"success": True, "complaints": complaints}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


@app.route("/api/manager/handle_return", methods=["POST"])
def handle_return():
    """Accept or decline a department return request."""
    data = request.get_json()
    manager_table_id = data.get("manager_table_id")
    complaint_id = data.get("complaint_id")
    decision = data.get("decision")  # 'Accept' or 'Decline'
    reply_note = data.get("reply_note", "")

    if not all([manager_table_id, complaint_id, decision]):
        return (
            jsonify({"error": "manager_table_id, complaint_id, decision are required"}),
            400,
        )
    if decision == "Decline" and not reply_note:
        return (
            jsonify({"error": "A reply note is required when declining a return"}),
            400,
        )

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT is_approved FROM managers WHERE id = %s", (manager_table_id,)
            )
            manager = cursor.fetchone()
            if not manager or not manager["is_approved"]:
                return jsonify({"error": "Manager not approved"}), 403

            cursor.execute(
                "SELECT id, department_id FROM complaints WHERE id = %s AND status = 'Return Pending'",
                (complaint_id,),
            )
            complaint = cursor.fetchone()
            if not complaint:
                return (
                    jsonify(
                        {"error": "Complaint not found or not in Return Pending state"}
                    ),
                    404,
                )

            if decision == "Accept":
                # Clear department assignment, reset to Registered
                cursor.execute(
                    "UPDATE complaints SET status = 'Registered', department_id = NULL WHERE id = %s",
                    (complaint_id,),
                )
                cursor.execute(
                    """
                    INSERT INTO complaint_status_history
                    (complaint_id, status, action_type, note, updated_by_role, updated_by_id)
                    VALUES (%s, 'Registered', 'Return Accepted', 'Manager accepted the return. Complaint is back in the queue.', 'Manager', %s)
                """,
                    (complaint_id, manager_table_id),
                )
                msg = "Return accepted. Complaint moved back to unassigned queue."

            elif decision == "Decline":
                # Reassign back to same department with Task Assigned status
                cursor.execute(
                    "SELECT name FROM departments WHERE id = %s",
                    (complaint["department_id"],),
                )
                dept = cursor.fetchone()
                dept_name = dept["name"] if dept else "the department"
                new_status = f"Task Assigned to {dept_name}"
                cursor.execute(
                    "UPDATE complaints SET status = %s WHERE id = %s",
                    (new_status, complaint_id),
                )
                cursor.execute(
                    """
                    INSERT INTO complaint_status_history
                    (complaint_id, status, action_type, note, updated_by_role, updated_by_id)
                    VALUES (%s, %s, 'Return Declined', %s, 'Manager', %s)
                """,
                    (complaint_id, new_status, reply_note, manager_table_id),
                )
                msg = "Return declined. Complaint reassigned to the department."
            else:
                return (
                    jsonify({"error": "Invalid decision. Must be Accept or Decline."}),
                    400,
                )

        connection.commit()
        return jsonify({"success": True, "message": msg}), 200
    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# --- AUTO-DELETE UNAPPROVED MANAGERS (24 HRS) ---
# Called as a background task or via a scheduler.
# Can also be triggered by hitting this endpoint from a cron job or
# Windows Task Scheduler.
@app.route("/api/admin/cleanup_unapproved", methods=["POST"])
def cleanup_unapproved_managers():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Find managers not approved within 24 hours
            
            cursor.execute("""
                SELECT id, email, name FROM managers
                WHERE is_approved = FALSE AND created_at < NOW() - INTERVAL 24 HOUR
            """)
            expired = cursor.fetchall()

            if not expired:
                return (
                    jsonify(
                        {"success": True, "message": "No expired managers to remove"}
                    ),
                    200,
                )

            SENDER_EMAIL = "urbanomaildelivery@gmail.com"
            SENDER_PASSWORD = "ddpnycqajyoubitl"

            for manager in expired:
                # Send rejection email
                try:
                    msg = EmailMessage()
                    msg.set_content(
                        f"Dear {manager['name'] or 'Applicant'},\n\n"
                        "Your registration request for Urbano Manager access has not been approved within 24 hours "
                        "and has been automatically removed.\n\n"
                        "Please contact the Urbano Admin if you believe this is an error.\n\nRegards,\nUrbano System"
                    )
                    msg["Subject"] = "Urbano Manager Registration - Not Approved"
                    msg["From"] = SENDER_EMAIL
                    msg["To"] = manager["email"]
                    server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    server.send_message(msg)
                    server.quit()
                except smtplib.SMTPException as smtp_err:
                    print(f"SMTP error sending rejection email to {manager['email']}: {smtp_err}")
                except socket.timeout:
                    print(f"SMTP timeout sending rejection email to {manager['email']}")
                except Exception as email_err:
                    print(f"Could not send rejection email to {manager['email']}: {email_err}")

            # Delete all expired unapproved managers
            cursor.execute("""
                DELETE FROM managers
                WHERE is_approved = FALSE AND created_at < NOW() - INTERVAL 24 HOUR
            """)

        connection.commit()
        return (
            jsonify(
                {
                    "success": True,
                    "message": f"{len(expired)} unapproved manager(s) removed",
                }
            ),
            200,
        )

    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()


# ADMIN MODULE


@app.route("/secure-admin-panel-hq-9921")
def admin_panel():
    return render_template("admin.html")


@app.route("/api/admin/stats", methods=["GET"])
def admin_stats():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM users")
            users = cursor.fetchone()["cnt"]
            cursor.execute("SELECT COUNT(*) as cnt FROM managers WHERE is_approved=1")
            managers = cursor.fetchone()["cnt"]
            cursor.execute("SELECT COUNT(*) as cnt FROM managers WHERE is_approved=0")
            pending_mgr = cursor.fetchone()["cnt"]
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM departments WHERE is_approved=1"
            )
            departments = cursor.fetchone()["cnt"]
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM departments WHERE is_approved=0"
            )
            pending_dept = cursor.fetchone()["cnt"]
            cursor.execute("SELECT COUNT(*) as cnt FROM complaints")
            total_complaints = cursor.fetchone()["cnt"]
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM complaints WHERE status='Registered'"
            )
            new_complaints = cursor.fetchone()["cnt"]
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM complaints WHERE status LIKE 'Task Assigned%%' OR status='Working'"
            )
            active_complaints = cursor.fetchone()["cnt"]
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM complaints WHERE status='Resolved'"
            )
            resolved_complaints = cursor.fetchone()["cnt"]
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM complaints WHERE status='Return Pending'"
            )
            return_complaints = cursor.fetchone()["cnt"]
        return jsonify(
            {
                "success": True,
                "stats": {
                    "users": users,
                    "managers": managers,
                    "pending_managers": pending_mgr,
                    "departments": departments,
                    "pending_departments": pending_dept,
                    "total_complaints": total_complaints,
                    "new_complaints": new_complaints,
                    "active_complaints": active_complaints,
                    "resolved_complaints": resolved_complaints,
                    "return_complaints": return_complaints,
                },
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/admin/system", methods=["GET"])
def admin_system():
    try:
        hostname = socket.gethostname()
        try:
            ip_addr = socket.gethostbyname(hostname)
        except:
            ip_addr = "127.0.0.1"
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0,8*6,8)][::-1])
        uptime = int(time.time() - SERVER_START_TIME)
        
        active_sessions = len(admin_sse_clients)
        if server_traffic_log:
            recent_ips = {entry['ip'] for entry in list(server_traffic_log)[:30]}
            active_sessions += len(recent_ips)

        return jsonify(
            {
                "success": True,
                "system": {
                    "recent_traffic": list(server_traffic_log),
                    "ip_address": ip_addr,
                    "mac_address": mac,
                    "port": 5000,
                    "server_name": hostname,
                    "active_sessions": active_sessions,
                    "uptime_seconds": uptime,
                    "status": "Healthy / Online",
                },
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/managers", methods=["GET"])
def admin_get_managers():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, manager_id, name, email, mobile_number, assigned_city,
                       is_approved, created_at,
                       COALESCE(is_online, 0) as is_online,
                       last_seen
                FROM managers ORDER BY created_at DESC
            """)
            managers = cursor.fetchall()
            for m in managers:
                if m.get("created_at"):
                    m["created_at"] = m["created_at"].strftime("%Y-%m-%d %H:%M")
                if m.get("last_seen"):
                    m["last_seen"] = m["last_seen"].strftime("%Y-%m-%d %H:%M:%S")
        return jsonify({"success": True, "managers": managers})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/admin/managers/update", methods=["POST"])
def admin_update_manager():
    data = request.get_json()
    mid = data.get("id")
    if not mid:
        return jsonify({"error": "id required"}), 400
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT name, email, assigned_city FROM managers WHERE id=%s", (mid,)
            )
            old_mgr = cursor.fetchone()
            if not old_mgr:
                return jsonify({"error": "Manager not found"}), 404

            fields, vals = [], []
            if "assigned_city" in data:
                fields.append("assigned_city=%s")
                vals.append(data["assigned_city"])
                if data["assigned_city"]:
                    # Ensure only one manager per city by removing assignment from others
                    cursor.execute(
                        "UPDATE managers SET assigned_city = NULL WHERE assigned_city = %s AND id != %s",
                        (data["assigned_city"], mid)
                    )
            if "is_approved" in data:
                fields.append("is_approved=%s")
                vals.append(data["is_approved"])
            if "assigned_city" in data and data.get("is_approved"):
                if not cursor.execute(
                    "SELECT manager_id FROM managers WHERE id=%s AND manager_id IS NOT NULL",
                    (mid,),
                ):
                    mgr_id = f"MGR-{uuid.uuid4().hex[:6].upper()}"
                    fields.append("manager_id=%s")
                    vals.append(mgr_id)
            if not fields:
                return jsonify({"error": "Nothing to update"}), 400
            vals.append(mid)
            cursor.execute(f"UPDATE managers SET {
                    ', '.join(fields)} WHERE id=%s", vals)
        conn.commit()

        if (
            "assigned_city" in data
            and old_mgr["assigned_city"] != data["assigned_city"]
        ):
            try:
                msg = EmailMessage()
                msg.set_content(f"Dear {
                        old_mgr['name']},\n\nYour assigned city has been updated to: {
                        data['assigned_city'] or 'None'}.\n\nRegards,\nUrbano Team")
                msg["Subject"] = "Urbano - Assigned City Updated"
                msg["From"] = "lalalatalala82@gmail.com"
                msg["To"] = old_mgr["email"]
                server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
                server.login("lalalatalala82@gmail.com", "zlpkyysopqxevybs")
                server.send_message(msg)
                server.quit()
            except Exception as e:
                print("Email error:", e)

        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/admin/managers/delete", methods=["POST"])
def admin_delete_manager():
    mid = request.get_json().get("id")
    if not mid:
        return jsonify({"error": "id required"}), 400
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name, email FROM managers WHERE id=%s", (mid,))
            mgr = cursor.fetchone()
            if not mgr:
                return jsonify({"error": "Not found"}), 404
            cursor.execute("DELETE FROM managers WHERE id=%s", (mid,))
        conn.commit()
        try:
            msg = EmailMessage()
            msg.set_content(
                f"Dear {
                    mgr['name']},\n\nYour account has been removed by the admin.\n\nRegards,\nUrbano Team"
            )
            msg["Subject"] = "Urbano - Account Removed"
            msg["From"] = "lalalatalala82@gmail.com"
            msg["To"] = mgr["email"]
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            server.login("lalalatalala82@gmail.com", "zlpkyysopqxevybs")
            server.send_message(msg)
            server.quit()
        except BaseException:
            pass
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/admin/departments", methods=["GET"])
def admin_get_departments():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, dept_id, name, email, contact_number, head_name,
                       assigned_city, is_approved, created_at,
                       COALESCE(is_online, 0) as is_online,
                       last_seen,
                       (SELECT COUNT(*) FROM complaints WHERE department_id=departments.id) as complaint_count
                FROM departments ORDER BY created_at DESC
            """)
            depts = cursor.fetchall()
            for d in depts:
                if d.get("created_at"):
                    d["created_at"] = d["created_at"].strftime("%Y-%m-%d %H:%M")
                if d.get("last_seen"):
                    d["last_seen"] = d["last_seen"].strftime("%Y-%m-%d %H:%M:%S")
        return jsonify({"success": True, "departments": depts})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/admin/departments/update", methods=["POST"])
def admin_update_department():
    data = request.get_json()
    did = data.get("id")
    if not did:
        return jsonify({"error": "id required"}), 400
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT name, email, assigned_city FROM departments WHERE id=%s", (did,)
            )
            old_dept = cursor.fetchone()
            if not old_dept:
                return jsonify({"error": "Department not found"}), 404

            fields, vals = [], []
            if "assigned_city" in data:
                fields.append("assigned_city=%s")
                vals.append(data["assigned_city"])
            if "is_approved" in data:
                fields.append("is_approved=%s")
                vals.append(data["is_approved"])
                if data["is_approved"]:
                    cursor.execute(
                        "SELECT dept_id FROM departments WHERE id=%s AND dept_id IS NOT NULL",
                        (did,),
                    )
                    if not cursor.fetchone():
                        dept_id_gen = f"DEPT-{uuid.uuid4().hex[:6].upper()}"
                        fields.append("dept_id=%s")
                        vals.append(dept_id_gen)
            if not fields:
                return jsonify({"error": "Nothing to update"}), 400
            vals.append(did)
            cursor.execute(f"UPDATE departments SET {
                    ', '.join(fields)} WHERE id=%s", vals)
        conn.commit()

        if (
            "assigned_city" in data
            and old_dept["assigned_city"] != data["assigned_city"]
        ):
            try:
                msg = EmailMessage()
                msg.set_content(f"Dear {
                        old_dept['name']},\n\nYour assigned city has been updated to: {
                        data['assigned_city'] or 'None'}.\n\nRegards,\nUrbano Team")
                msg["Subject"] = "Urbano - Assigned City Updated"
                msg["From"] = "lalalatalala82@gmail.com"
                msg["To"] = old_dept["email"]
                server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
                server.login("lalalatalala82@gmail.com", "zlpkyysopqxevybs")
                server.send_message(msg)
                server.quit()
            except Exception as e:
                print("Email error:", e)

        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/admin/departments/delete", methods=["POST"])
def admin_delete_department():
    did = request.get_json().get("id")
    if not did:
        return jsonify({"error": "id required"}), 400
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name, email FROM departments WHERE id=%s", (did,))
            dept = cursor.fetchone()
            if not dept:
                return jsonify({"error": "Not found"}), 404
            cursor.execute("DELETE FROM departments WHERE id=%s", (did,))
        conn.commit()
        try:
            msg = EmailMessage()
            msg.set_content(
                f"Dear {
                    dept['name']},\n\nYour account has been removed by the admin.\n\nRegards,\nUrbano Team"
            )
            msg["Subject"] = "Urbano - Account Removed"
            msg["From"] = "lalalatalala82@gmail.com"
            msg["To"] = dept["email"]
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            server.login("lalalatalala82@gmail.com", "zlpkyysopqxevybs")
            server.send_message(msg)
            server.quit()
        except BaseException:
            pass
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/admin/complaints", methods=["GET"])
def admin_get_complaints():
    city = request.args.get("city", "")
    status = request.args.get("status", "")
    dept_id = request.args.get("dept_id", "")
    search = request.args.get("search", "")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            conditions = []
            params = []
            if city:
                conditions.append("c.city=%s")
                params.append(city)
            if status:
                if status in ('Working', 'Active'):
                    conditions.append("(c.status LIKE 'Task Assigned%%' OR c.status = 'Working')")
                else:
                    conditions.append("c.status=%s")
                    params.append(status)
            if dept_id:
                conditions.append("c.department_id=%s")
                params.append(dept_id)
            if search:
                conditions.append("(c.title LIKE %s OR c.details LIKE %s)")
                params += [f"%{search}%", f"%{search}%"]
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            cursor.execute(
                f"""
                SELECT c.id, c.title, c.details, c.title_en, c.details_en, c.original_lang, c.status, c.city, c.address, c.landmark, c.latitude, c.longitude, c.created_at, c.department_id,
                       d.name as department_name, u.name as user_name, u.email as user_email,
                       (SELECT csh.created_at FROM complaint_status_history csh WHERE csh.complaint_id = c.id AND csh.action_type LIKE 'Task Assigned%%' ORDER BY csh.created_at DESC LIMIT 1) as assigned_at
                FROM complaints c
                LEFT JOIN departments d ON c.department_id=d.id
                LEFT JOIN users u ON c.user_id=u.id
                {where}
                ORDER BY c.created_at DESC LIMIT 500
            """,
                params,
            )
            complaints = cursor.fetchall()
            for c in complaints:
                if c.get("created_at"):
                    c["created_at"] = c["created_at"].strftime("%Y-%m-%d %H:%M")
                if c.get("assigned_at"):
                    c["assigned_at"] = c["assigned_at"].strftime("%Y-%m-%d %H:%M")
            # Cities and departments for filter dropdowns
            cursor.execute("SELECT DISTINCT city FROM complaints ORDER BY city")
            cities = [r["city"] for r in cursor.fetchall() if r["city"]]
            cursor.execute(
                "SELECT id, name FROM departments WHERE is_approved=1 ORDER BY name"
            )
            depts = cursor.fetchall()
        return jsonify(
            {
                "success": True,
                "complaints": complaints,
                "cities": cities,
                "departments": depts,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/admin/users", methods=["GET"])
def admin_get_users():
    search = request.args.get("search", "")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cond = "WHERE name LIKE %s OR email LIKE %s" if search else ""
            params = [f"%{search}%", f"%{search}%"] if search else []
            cursor.execute(
                f"""
                SELECT id, name, email, mobile_number, address, created_at,
                       (SELECT COUNT(*) FROM complaints WHERE user_id=users.id) as complaint_count
                FROM users {cond} ORDER BY created_at DESC
            """,
                params,
            )
            users = cursor.fetchall()
            for u in users:
                if u.get("created_at"):
                    u["created_at"] = u["created_at"].strftime("%Y-%m-%d %H:%M")
        return jsonify({"success": True, "users": users})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/admin/users/delete", methods=["POST"])
def admin_delete_user():
    uid = request.get_json().get("id")
    if not uid:
        return jsonify({"error": "id required"}), 400
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id=%s", (uid,))
        conn.commit()
        send_status_update_email(cid, "Admin")
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/admin/complaints/delete", methods=["POST"])
def admin_delete_complaint():
    cid = request.get_json().get("id")
    if not cid:
        return jsonify({"error": "id required"}), 400
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM complaint_status_history WHERE complaint_id=%s", (cid,)
            )
            cursor.execute("DELETE FROM complaints WHERE id=%s", (cid,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/admin/complaints/update", methods=["POST"])
def admin_update_complaint():
    data = request.get_json()
    cid = data.get("id")
    status = data.get("status")
    dept_id = data.get("department_id") or None
    note = data.get("note", "").strip()
    if not note:
        return jsonify({"error": "Admin note is required"}), 400

    if not cid:
        return jsonify({"error": "id required"}), 400
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE complaints SET status=%s, department_id=%s WHERE id=%s",
                (status, dept_id, cid),
            )
            # Also log in history
            cursor.execute(
                """
                INSERT INTO complaint_status_history (complaint_id, status, action_type, note, updated_by_role, created_at)
                VALUES (%s, %s, 'Admin Update', %s, 'Admin', NOW())
            """,
                (cid, status, note),
            )
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


# MESSAGING API
@app.route('/api/messages/send', methods=['POST'])
def send_message():
    data = request.json
    sender_role = data.get('sender_role')
    sender_id = data.get('sender_id')
    receiver_role = data.get('receiver_role')
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    if not all([sender_role, sender_id, receiver_role, receiver_id, content]):
        return jsonify({'success': False, 'error': 'Missing required fields'})
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                '''INSERT INTO messages (sender_role, sender_id, receiver_role, receiver_id, content)
                   VALUES (%s, %s, %s, %s, %s)''',
                (sender_role, sender_id, receiver_role, receiver_id, content)
            )
            conn.commit()
            if receiver_role == "admin" or sender_role == "admin":
                notify_admin({"type": "message"})
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/messages/fetch', methods=['GET'])
def fetch_messages():
    role1 = request.args.get('role1')
    id1 = request.args.get('id1')
    role2 = request.args.get('role2')
    id2 = request.args.get('id2')
    
    if not all([role1, id1, role2, id2]):
        return jsonify({'success': False, 'error': 'Missing required fields'})
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                '''UPDATE messages SET is_read = 1 
                   WHERE receiver_role = %s AND receiver_id = %s AND sender_role = %s AND sender_id = %s''',
                (role1, id1, role2, id2)
            )
            conn.commit()
            
            query = '''SELECT * FROM messages 
                   WHERE ((sender_role = %s AND sender_id = %s AND receiver_role = %s AND receiver_id = %s)
                      OR (sender_role = %s AND sender_id = %s AND receiver_role = %s AND receiver_id = %s))'''
            
            if role1 != 'admin':
                query += ' AND cleared_by_client = 0'
                
            query += ' ORDER BY created_at ASC'
            
            cursor.execute(query, (role1, id1, role2, id2, role2, id2, role1, id1))
            rows = cursor.fetchall()
            return jsonify({'success': True, 'messages': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/messages/clear', methods=['POST'])
def clear_messages():
    data = request.json
    role = data.get('role')
    user_id = data.get('id')
    
    if not all([role, user_id]):
        return jsonify({'success': False, 'error': 'Missing required fields'})
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                '''UPDATE messages SET cleared_by_client = 1 
                   WHERE (sender_role = %s AND sender_id = %s AND receiver_role = 'admin')
                      OR (receiver_role = %s AND receiver_id = %s AND sender_role = 'admin')''',
                (role, user_id, role, user_id)
            )
            conn.commit()
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/messages/threads', methods=['GET'])
def get_message_threads():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT DISTINCT sender_role, sender_id 
                FROM messages WHERE receiver_role = 'admin'
                UNION
                SELECT DISTINCT receiver_role, receiver_id 
                FROM messages WHERE sender_role = 'admin'
            ''')
            threads = cursor.fetchall()
            
            enriched = []
            for t in threads:
                role = t['sender_role']
                cid = t['sender_id']
                cursor.execute(
                    "SELECT COUNT(*) as unread_count FROM messages WHERE sender_role=%s AND sender_id=%s AND receiver_role='admin' AND is_read=0",
                    (role, cid)
                )
                unread = cursor.fetchone()['unread_count']
                
                if role == 'manager':
                    cursor.execute("SELECT name, assigned_city, is_online, last_seen FROM managers WHERE id = %s", (cid,))
                    m = cursor.fetchone()
                    if m:
                        ls = m['last_seen'].strftime("%Y-%m-%d %H:%M:%S") if m['last_seen'] else None
                        enriched.append({'role': role, 'id': cid, 'name': m['name'], 'city': m['assigned_city'], 'unread_count': unread, 'is_online': m['is_online'], 'last_seen': ls})
                elif role == 'department':
                    cursor.execute("SELECT name, assigned_city, is_online, last_seen FROM departments WHERE id = %s", (cid,))
                    d = cursor.fetchone()
                    if d:
                        ls = d['last_seen'].strftime("%Y-%m-%d %H:%M:%S") if d['last_seen'] else None
                        enriched.append({'role': role, 'id': cid, 'name': d['name'], 'city': d['assigned_city'], 'unread_count': unread, 'is_online': d['is_online'], 'last_seen': ls})
                        
            return jsonify({'success': True, 'threads': enriched})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

# ════════════════════════════════════════════════════════
#  ONLINE STATUS — ensure DB columns exist
# ════════════════════════════════════════════════════════
def ensure_online_columns():
    """Add is_online and last_seen columns to managers and departments if missing."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for table in ("managers", "departments"):
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN is_online TINYINT(1) NOT NULL DEFAULT 0")
                except Exception:
                    pass  # Already exists
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN last_seen DATETIME NULL")
                except Exception:
                    pass  # Already exists
        conn.commit()
    except Exception as e:
        print(f"[online_columns] Warning: {e}")
    finally:
        conn.close()

try:
    ensure_online_columns()
except Exception:
    pass


# ════════════════════════════════════════════════════════
#  LOGOUT STATUS — mark offline on logout
# ════════════════════════════════════════════════════════
@app.route("/api/logout_status", methods=["POST"])
def logout_status():
    """Called when manager/department logs out — sets is_online=0."""
    data = request.get_json(force=True, silent=True) or {}
    role = data.get("role")   # 'manager' | 'department'
    entity_id = data.get("id")
    if not role or not entity_id:
        return jsonify({"success": False, "error": "role and id required"}), 400
    table = "managers" if role == "manager" else "departments"
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET is_online=0, last_seen=NOW() WHERE id=%s",
                (entity_id,)
            )
        conn.commit()
        notify_admin({"type": "status"})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


# ════════════════════════════════════════════════════════
#  ADMIN ONLINE STATUS
# ════════════════════════════════════════════════════════
@app.route("/api/admin/online_status", methods=["GET"])
def admin_online_status():
    """Returns all approved managers and departments with online/last-seen status."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, name, assigned_city as city,
                       COALESCE(is_online, 0) as is_online,
                       last_seen
                FROM managers
                WHERE is_approved = 1
                ORDER BY is_online DESC, name ASC
            """)
            managers = cursor.fetchall()
            for m in managers:
                m["role"] = "manager"
                if m.get("last_seen"):
                    m["last_seen"] = m["last_seen"].strftime("%Y-%m-%dT%H:%M:%S")

            cursor.execute("""
                SELECT id, name, assigned_city as city,
                       COALESCE(is_online, 0) as is_online,
                       last_seen
                FROM departments
                WHERE is_approved = 1
                ORDER BY is_online DESC, name ASC
            """)
            depts = cursor.fetchall()
            for d in depts:
                d["role"] = "department"
                if d.get("last_seen"):
                    d["last_seen"] = d["last_seen"].strftime("%Y-%m-%dT%H:%M:%S")

        entities = managers + depts
        # Sort: online first
        entities.sort(key=lambda x: (0 if x["is_online"] else 1, x["name"]))
        return jsonify({"success": True, "entities": entities})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route('/api/admin/complaint_media', methods=['GET'])
def admin_complaint_media():
    cid = request.args.get('complaint_id')
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT media_path FROM complaint_media WHERE complaint_id=%s", (cid,))
            return jsonify({'success': True, 'media': [r['media_path'] for r in cursor.fetchall()]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/api/admin/sse')
def admin_sse():
    def stream():
        q = queue.Queue(maxsize=20)
        admin_sse_clients.append(q)
        try:
            while True:
                try:
                    msg = q.get(timeout=3)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            if q in admin_sse_clients:
                admin_sse_clients.remove(q)
    return Response(stream(), mimetype="text/event-stream")

if __name__ == "__main__":
    # host='0.0.0.0' makes the server accessible from other devices on the Wi-Fi network
    # use_reloader=False prevents the Werkzeug reloader from spawning a second process,
    # which was causing double/triple OTP emails on button click.
    app.run(host="0.0.0.0", port=80, debug=False, use_reloader=False)
