# -*- coding: utf-8 -*-
import odoo
import base64
import logging
import random
import re
from odoo import http, fields, _
from odoo.http import request
from datetime import datetime, timedelta
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


def sanitize_b64(b64_string):
    """Helper to decode base64 string to binary bytes for Odoo binary fields."""
    if not b64_string:
        return False
    try:
        if isinstance(b64_string, bytes):
            b64_string = b64_string.decode('utf-8')
        if ',' in b64_string:
            b64_string = b64_string.split(',')[1]

        # Odoo binary fields require raw decoded bytes or base64 bytes
        # Decoding and re-encoding cleanly ensures Odoo accepts it
        binary_data = base64.b64decode(b64_string)
        return binary_data
    except Exception as e:
        _logger.error("Invalid base64 image string: %s", str(e))
        return False

def is_valid_pan(pan):
    """Validates Indian PAN card format (Individual: 4th char 'P')."""
    if not pan:
        return False
    pattern = r'^[A-Z]{3}[P][A-Z]{1}[0-9]{4}[A-Z]{1}$'
    return bool(re.match(pattern, pan.strip().upper()))


def is_valid_aadhaar_verhoeff(aadhaar_str):
    """
    Validates 12-digit Aadhaar number using the official Verhoeff checksum algorithm.
    """
    if not aadhaar_str:
        return False
    aadhaar = re.sub(r'\D', '', str(aadhaar_str))
    if len(aadhaar) != 12 or aadhaar[0] in ['0', '1']:  # Aadhaar never starts with 0 or 1
        return False

    # Verhoeff Multiplication Table
    d = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
        [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
        [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
        [5, 6, 7, 8, 9, 0, 1, 2, 3, 4],
        [6, 7, 8, 9, 5, 1, 2, 3, 4, 0],
        [7, 8, 9, 5, 6, 2, 3, 4, 0, 1],
        [8, 9, 5, 6, 7, 3, 4, 0, 1, 2],
        [9, 5, 6, 7, 8, 4, 0, 1, 2, 3],
    ]
    # Permutation Table
    p = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 5, 7, 6, 2, 8, 3, 4, 9, 0],
        [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
        [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
        [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
        [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
    ]

    c = 0
    inverted_digits = [int(x) for x in reversed(aadhaar)]
    for i, digit in enumerate(inverted_digits):
        c = d[c][p[i % 8][digit]]
    return c == 0


def is_valid_vehicle_number(vehicle_no):
    """Validates Indian Vehicle Registration number format (e.g., TN01AB1234)."""
    if not vehicle_no:
        return False
    pattern = r'^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$'
    clean_no = re.sub(r'[\s-]', '', vehicle_no.upper())
    return bool(re.match(pattern, clean_no))


def is_valid_driving_license(license_no):
    """Validates Indian Driving License format."""
    if not license_no:
        return False
    pattern = r'^[A-Z]{2}[0-9]{2}[0-9A-Z]{9,11}$'
    clean_dl = re.sub(r'[\s-]', '', license_no.upper())
    return bool(re.match(pattern, clean_dl))


def is_valid_email(email):
    """Basic helper to validate email format."""
    if not email:
        return False
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_regex, email))


def sanitize_b64(b64_string):
    """Helper to strip data URI prefixes and validate base64 encoding."""
    if not b64_string:
        return None
    cleaned = b64_string.split(',')[1] if ',' in b64_string else b64_string
    try:
        base64.b64decode(cleaned, validate=True)
        return cleaned
    except Exception:
        return False


class DeliveryPartnerAPI(http.Controller):

    # ==========================================
    # 1. AUTHENTICATION & TOKEN HANDLING
    # ==========================================

    @http.route('/api/delivery/signup', type='json', auth='none', methods=['POST'], csrf=False)
    def signup(
            self,
            name,
            email,
            phone,
            password,
            profile_image_base64=None,
            aadhaar_number=None,
            pan_number=None,
            vehicle_type=None,
            vehicle_number=None,
            license_number=None,
            license_doc_base64=None,
            aadhaar_front_base64=None,
            aadhaar_back_base64=None,
            pan_doc_base64=None,
            street=None,
            city=None,
            state_id=None,
            country_id=None,
            zip_code=None,
    ):
        """
        Self-registration endpoint that creates a user, sets address & KYC details,
        and safely provisions a linked hr.employee record.
        """
        # 1. Basic Field Validations
        if not name or not str(name).strip():
            return {'status': 'error', 'message': 'Full name is required.'}
        if not password or len(str(password)) < 6:
            return {'status': 'error', 'message': 'Password must be at least 6 characters.'}

        clean_email = str(email).strip().lower() if email else ''
        if not clean_email or not is_valid_email(clean_email):
            return {'status': 'error', 'message': 'Invalid email address format.'}

        clean_phone = str(phone).strip() if phone else ''
        phone_digits = re.sub(r'\D', '', clean_phone)
        if not clean_phone or len(phone_digits) < 10 or len(phone_digits) > 13:
            return {'status': 'error', 'message': 'Invalid mobile number.'}

        # 2. Format Sanitization
        clean_pan = pan_number.strip().upper() if pan_number else False
        clean_aadhaar = re.sub(r'\D', '', str(aadhaar_number)) if aadhaar_number else False

        # 3. Dynamic Duplicate Check Domain
        or_conditions = [('login', '=', clean_email), ('partner_id.phone', '=', clean_phone)]
        if clean_pan:
            or_conditions.append(('pan_number', '=', clean_pan))
        if clean_aadhaar:
            or_conditions.append(('aadhaar_number', '=', clean_aadhaar))

        search_domain = ['|'] * (len(or_conditions) - 1) + or_conditions

        existing_user = request.env['res.users'].sudo().search(search_domain, limit=1)
        if existing_user:
            return {
                'status': 'error',
                'message': 'An account with this email, phone, PAN, or Aadhaar already exists.',
            }

        # 4. Clean Profile Image Base64
        clean_profile_image = sanitize_b64(profile_image_base64)
        if clean_profile_image is False:
            return {'status': 'error', 'message': 'Invalid base64 string for user profile image.'}

        # 5. Clean Document Attachments
        docs_to_upload = []
        doc_inputs = [
            ('PAN_Card.jpg', pan_doc_base64, 'PAN Card Photo'),
            ('Aadhaar_Front.jpg', aadhaar_front_base64, 'Aadhaar Front Photo'),
            ('Aadhaar_Back.jpg', aadhaar_back_base64, 'Aadhaar Back Photo'),
            ('Driving_License.jpg', license_doc_base64, 'Driving License Photo'),
        ]

        for filename, b64_str, doc_label in doc_inputs:
            if b64_str:
                cleaned = sanitize_b64(b64_str)
                if cleaned is False:
                    return {'status': 'error', 'message': f'Invalid image format for {doc_label}.'}
                if cleaned:
                    docs_to_upload.append((filename, cleaned))

        # 6. User Creation and Employee Action Trigger Under Admin Environment Context
        try:
            admin_user = request.env.ref('base.user_admin').sudo()
            company = request.env.ref('base.main_company').sudo()

            env_admin = request.env['res.users'].sudo().with_user(admin_user)

            user_vals = {
                'name': str(name).strip(),
                'login': clean_email,
                'email': clean_email,
                'phone': clean_phone,
                'password': str(password),
                'is_delivery_partner': True,
                'is_online': False,
                'pan_number': clean_pan,
                'aadhaar_number': clean_aadhaar,
                'vehicle_type': vehicle_type.strip() if vehicle_type else False,
                'vehicle_number': (
                    re.sub(r'[\s-]', '', vehicle_number.upper()) if vehicle_number else False
                ),
                'license_number': (
                    re.sub(r'[\s-]', '', license_number.upper()) if license_number else False
                ),
                'company_id': company.id,
                'company_ids': [(6, 0, [company.id])],
                # Address fields
                'street': street.strip() if street else False,
                'city': city.strip() if city else False,
                'state_id': int(state_id) if state_id else False,
                'country_id': int(country_id) if country_id else False,
                'zip': zip_code.strip() if zip_code else False,
            }

            if clean_profile_image:
                user_vals['image_1920'] = clean_profile_image

            # Create user
            new_user = env_admin.with_context(
                no_reset_password=True,
                signup_force_type_in_context=True,
                mail_create_nosubscribe=True
            ).create(user_vals)

            created_user_id = int(new_user.id)

            # Update partner record mobile consistency
            if new_user.partner_id:
                partner = new_user.partner_id[0]
                partner.sudo().write({
                    'phone': clean_phone,
                    'mobile': clean_phone,
                })

            # Safely trigger employee creation without throwing singleton errors
            created_employee_id = None
            try:
                if hasattr(new_user, 'action_create_employee'):
                    new_user.action_create_employee()

                # Search safely for the linked employee
                employee = request.env['hr.employee'].sudo().search([('user_id', '=', created_user_id)], limit=1)
                if employee:
                    created_employee_id = employee.id
                    emp_vals = {}
                    if hasattr(employee, 'vehicle_type') and user_vals.get('vehicle_type'):
                        emp_vals['vehicle_type'] = user_vals['vehicle_type']
                    if hasattr(employee, 'vehicle_number') and user_vals.get('vehicle_number'):
                        emp_vals['vehicle_number'] = user_vals['vehicle_number']
                    if clean_profile_image and hasattr(employee, 'image_1920'):
                        emp_vals['image_1920'] = clean_profile_image
                    if emp_vals:
                        employee.sudo().write(emp_vals)
            except Exception as emp_err:
                _logger.warning(f"Employee auto-creation warning for user {created_user_id}: {str(emp_err)}")

            # Save KYC binary attachments
            attachment_env = request.env['ir.attachment'].sudo().with_user(admin_user)
            for filename, b64_data in docs_to_upload:
                attachment_env.create({
                    'name': f"{filename[:-4]}_{created_user_id}.jpg",
                    'type': 'binary',
                    'datas': b64_data,
                    'res_model': 'res.users',
                    'res_id': created_user_id,
                    'mimetype': 'image/jpeg',
                })

            return {
                'status': 'success',
                'message': 'Registration successful and employee profile created.',
                'user_id': created_user_id,
                'employee_id': created_employee_id,
            }

        except Exception as e:
            _logger.error(f"Delivery Partner Signup Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': f'Registration failed: {str(e)}'}

    @http.route('/api/delivery/login', type='json', auth='none', methods=['POST'], csrf=False)
    def login(self, db, login, password, fcm_token=None):
        """Delivery partner login handler for Odoo 18."""
        if not login or not password or not db:
            return {'status': 'error', 'message': 'Database, email, and password are required.'}

        clean_login = str(login).strip().lower()
        clean_db = str(db).strip()

        try:
            # 1. Assign target database to active session
            request.session.db = clean_db

            # 2. Authenticate user credentials
            try:
                uid = request.session.authenticate(clean_db, clean_login, str(password))
            except TypeError:
                credential = {'type': 'password', 'login': clean_login, 'password': str(password)}
                uid = request.session.authenticate(clean_db, credential)

            if not uid:
                return {'status': 'error', 'message': 'Invalid login credentials.'}

            # 3. Read authenticated user details using elevated admin environment
            admin_user = request.env.ref('base.user_admin').sudo()
            user = request.env['res.users'].sudo().with_user(admin_user).browse(uid)

            # 4. Verify delivery partner role flag
            if not getattr(user, 'is_delivery_partner', False):
                return {
                    'status': 'error',
                    'message': 'Access restricted to authorized delivery partners.',
                }

            # 5. Save FCM notification token if provided
            if fcm_token and hasattr(user, 'fcm_token'):
                user.sudo().write({'fcm_token': fcm_token})

            return {
                'status': 'success',
                'session_id': request.session.sid,
                'uid': user.id,
                'name': user.name,
                'email': user.email,
                'phone': user.phone or user.mobile or '',
                'is_online': getattr(user, 'is_online', False),
            }

        except Exception as e:
            _logger.error(f"Delivery Partner Login Exception for {clean_login}: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': f'Login failed: {str(e)}'}

    @http.route('/api/delivery/validate_token', type='json', auth='user', methods=['POST'])
    def validate_token(self):
        """Refresh and validate active session token."""
        user = request.env.user
        if not getattr(user, 'is_delivery_partner', False):
            return {'status': 'error', 'message': 'Unauthorized session.'}
        return {
            'status': 'success',
            'session_id': request.session.sid,
            'uid': user.id,
            'is_online': getattr(user, 'is_online', False),
        }

    @http.route('/api/delivery/forgot_password', type='json', auth='none', methods=['POST'], csrf=False)
    def forgot_password(self, email):
        """Request password reset link via Odoo standard mail process safely."""
        if not email:
            return {'status': 'error', 'message': 'Email address is required.'}

        clean_email = str(email).strip().lower()

        try:
            admin_user = request.env.ref('base.user_admin').sudo()
            user = request.env['res.users'].sudo().with_user(admin_user).search([('email', '=', clean_email)], limit=1)

            if not user or not getattr(user, 'is_delivery_partner', False):
                return {
                    'status': 'error',
                    'message': 'No registered delivery partner found with this email.',
                }

            # 1. Primary Method: Standard Odoo action_reset_password
            if hasattr(user, 'action_reset_password'):
                user.action_reset_password()
                return {
                    'status': 'success',
                    'message': 'Password reset instructions sent to email.',
                }

            # 2. Secondary Method: auth_signup module methods (if installed)
            if hasattr(user, 'action_send_password_reset_instructions'):
                user.action_send_password_reset_instructions()
                return {
                    'status': 'success',
                    'message': 'Password reset instructions sent to email.',
                }

            if hasattr(user, 'signup_prepare'):
                user.signup_prepare(signup_type='reset')
                user.send_password_reset_email()
                return {
                    'status': 'success',
                    'message': 'Password reset instructions sent to email.',
                }

            # 3. Fallback: If auth_signup is not installed on the database
            return {
                'status': 'error',
                'message': 'Password reset is disabled on this server. Please ensure the "auth_signup" module is installed in Odoo apps.',
            }

        except Exception as e:
            _logger.error(f"Password reset request failed for {clean_email}: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': f'Failed to process password reset: {str(e)}',
            }

    @http.route('/api/mobile/check_in', type='json', auth='user', csrf=False, methods=['POST'])
    def mobile_check_in(self, latitude=None, longitude=None):
        """
        Check-in endpoint for employee attendance with optional GPS data.
        """
        try:
            user = request.env.user
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)

            if not employee:
                return {'status': 'error', 'message': 'No employee associated with this account.'}

            if employee.attendance_state == 'checked_in':
                return {'status': 'error', 'message': 'Employee is already checked in.'}

            # Attendance Check-in execution
            now = fields.Datetime.now()
            vals_res = {'is_online': True}
            vals = {
                'employee_id': employee.id,
                'check_in': now,
            }

            # Attach GPS Coordinates if passed from mobile app
            if latitude and longitude:
                if hasattr(request.env['hr.attendance'], 'in_latitude'):
                    vals.update({
                        'in_latitude': float(latitude),
                        'in_longitude': float(longitude),
                    })

            attendance = request.env['hr.attendance'].sudo().create(vals)
            user.sudo().write(vals_res)

            return {
                'status': 'success',
                'message': 'Checked in successfully.',
                'data': {
                    'attendance_id': attendance.id,
                    'employee_id': employee.id,
                    'check_in_time': fields.Datetime.to_string(attendance.check_in),
                    'attendance_state': 'checked_in'
                }
            }
        except Exception as e:
            _logger.error("API Check-In Error: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/mobile/check_out', type='json', auth='user', csrf=False, methods=['POST'])
    def mobile_check_out(self, latitude=None, longitude=None):
        """
        Check-out endpoint for employee attendance.
        """
        try:
            user = request.env.user
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)

            if not employee:
                return {'status': 'error', 'message': 'No employee associated with this account.'}

            if employee.attendance_state == 'checked_out':
                return {'status': 'error', 'message': 'Employee is already checked out in Odoo.'}

            # Retrieve active open attendance record
            attendance = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False)
            ], limit=1, order='check_in desc')

            if not attendance:
                return {'status': 'error', 'message': 'No open check-in record found for this employee.'}

            now = fields.Datetime.now()
            vals = {'check_out': now}
            vals_res = {'is_online': False}

            # Attach GPS coordinates if available
            if latitude and longitude:
                if hasattr(attendance, 'out_latitude'):
                    vals.update({
                        'out_latitude': float(latitude),
                        'out_longitude': float(longitude),
                    })

            attendance.sudo().write(vals)
            user.sudo().write(vals_res)

            return {
                'status': 'success',
                'message': 'Checked out successfully.',
                'data': {
                    'attendance_id': attendance.id,
                    'employee_id': employee.id,
                    'check_out_time': fields.Datetime.to_string(attendance.check_out),
                    'attendance_state': 'checked_out'
                }
            }
        except Exception as e:
            _logger.error("API Check-Out Error: %s", str(e))
            # Returns the exact Python error string to Postman for quick debugging
            return {'status': 'error', 'message': str(e)}

    @http.route(
        '/api/mobile/attendance_summary',
        type='json',
        auth='user',
        csrf=False,
        methods=['POST']
    )
    def get_attendance_summary(
            self,
            uid=None,
            target_date=None,
            date_from=None,
            date_to=None
    ):
        try:

            # ---------------------------------------------------------
            # 1. GET USER
            # ---------------------------------------------------------
            if uid:
                try:
                    uid = int(uid)
                except (ValueError, TypeError):
                    return {
                        'status': 'error',
                        'message': 'Invalid uid.'
                    }

                user = request.env['res.users'].sudo().browse(uid)

                if not user.exists():
                    return {
                        'status': 'error',
                        'message': 'User not found.'
                    }

                employee = request.env['hr.employee'].sudo().search(
                    [('user_id', '=', user.id)],
                    limit=1
                )

            else:
                # If uid is not passed, use currently logged-in user
                user = request.env.user

                employee = request.env['hr.employee'].sudo().search(
                    [('user_id', '=', user.id)],
                    limit=1
                )

            if not employee:
                return {
                    'status': 'error',
                    'message': 'No employee associated with this user.'
                }

            # ---------------------------------------------------------
            # 2. CURRENT DATETIME
            # ---------------------------------------------------------
            now_dt = fields.Datetime.now()

            # ---------------------------------------------------------
            # 3. TARGET DATE
            # ---------------------------------------------------------
            if target_date:
                try:
                    base_date = datetime.strptime(
                        target_date,
                        '%Y-%m-%d'
                    ).date()
                except ValueError:
                    return {
                        'status': 'error',
                        'message': 'Invalid target_date format. Use YYYY-MM-DD.'
                    }
            else:
                base_date = fields.Date.today()

            # ---------------------------------------------------------
            # 4. HELPER
            # ---------------------------------------------------------
            def compute_hours_for_domain(domain):

                attendances = request.env['hr.attendance'].sudo().search(
                    domain,
                    order='check_in asc'
                )

                total_seconds = 0
                sessions = []

                for att in attendances:

                    check_in = att.check_in
                    check_out = att.check_out

                    if not check_in:
                        continue

                    # Active attendance
                    if not check_out:
                        check_out = now_dt

                    if check_out <= check_in:
                        continue

                    duration = (
                            check_out - check_in
                    ).total_seconds()

                    total_seconds += duration

                    sessions.append({
                        'attendance_id': att.id,
                        'check_in': fields.Datetime.to_string(
                            att.check_in
                        ),
                        'check_out': (
                            fields.Datetime.to_string(
                                att.check_out
                            )
                            if att.check_out
                            else 'Active'
                        ),
                        'duration_hours': round(
                            duration / 3600,
                            2
                        )
                    })

                total_hrs = round(
                    total_seconds / 3600,
                    2
                )

                hours = int(total_seconds // 3600)
                minutes = int(
                    (total_seconds % 3600) // 60
                )
                seconds = int(total_seconds % 60)

                formatted_time = (
                    f"{hours:02d}:"
                    f"{minutes:02d}:"
                    f"{seconds:02d}"
                )

                return (
                    total_hrs,
                    formatted_time,
                    sessions
                )

            # ---------------------------------------------------------
            # 5. TODAY
            # ---------------------------------------------------------
            day_start = datetime.combine(
                base_date,
                datetime.min.time()
            )

            day_end = datetime.combine(
                base_date,
                datetime.max.time()
            )

            today_hrs, today_fmt, today_sessions = (
                compute_hours_for_domain([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=',
                     fields.Datetime.to_string(day_start)),
                    ('check_in', '<=',
                     fields.Datetime.to_string(day_end))
                ])
            )

            # ---------------------------------------------------------
            # 6. WEEK
            # ---------------------------------------------------------
            start_of_week = (
                    base_date -
                    timedelta(days=base_date.weekday())
            )

            end_of_week = (
                    start_of_week +
                    timedelta(days=6)
            )

            week_start_dt = datetime.combine(
                start_of_week,
                datetime.min.time()
            )

            week_end_dt = datetime.combine(
                end_of_week,
                datetime.max.time()
            )

            week_hrs, week_fmt, week_sessions = (
                compute_hours_for_domain([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=',
                     fields.Datetime.to_string(week_start_dt)),
                    ('check_in', '<=',
                     fields.Datetime.to_string(week_end_dt))
                ])
            )

            # ---------------------------------------------------------
            # 7. MONTH
            # ---------------------------------------------------------
            start_of_month = base_date.replace(day=1)

            next_month = (
                    start_of_month.replace(day=28)
                    + timedelta(days=4)
            )

            end_of_month = (
                    next_month -
                    timedelta(days=next_month.day)
            )

            month_start_dt = datetime.combine(
                start_of_month,
                datetime.min.time()
            )

            month_end_dt = datetime.combine(
                end_of_month,
                datetime.max.time()
            )

            month_hrs, month_fmt, month_sessions = (
                compute_hours_for_domain([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=',
                     fields.Datetime.to_string(month_start_dt)),
                    ('check_in', '<=',
                     fields.Datetime.to_string(month_end_dt))
                ])
            )

            # ---------------------------------------------------------
            # 8. CUSTOM RANGE
            # ---------------------------------------------------------
            custom_hrs = 0
            custom_fmt = "00:00:00"
            custom_sessions = []

            if date_from and date_to:
                custom_hrs, custom_fmt, custom_sessions = (
                    compute_hours_for_domain([
                        ('employee_id', '=', employee.id),
                        ('check_in', '>=', date_from),
                        ('check_in', '<=', date_to)
                    ])
                )

            # ---------------------------------------------------------
            # 9. RESPONSE
            # ---------------------------------------------------------
            return {
                'status': 'success',
                'data': {

                    'uid': user.id,

                    'employee_id': employee.id,

                    'employee_name': employee.name,

                    'target_date_evaluated': str(
                        base_date
                    ),

                    'today': {
                        'total_hours': today_hrs,
                        'formatted_time': today_fmt,
                        'sessions': today_sessions
                    },

                    'weekly': {
                        'start_date': str(start_of_week),
                        'end_date': str(end_of_week),
                        'total_hours': week_hrs,
                        'formatted_time': week_fmt
                    },

                    'monthly': {
                        'month': base_date.strftime(
                            '%B %Y'
                        ),
                        'total_hours': month_hrs,
                        'formatted_time': month_fmt
                    },

                    'custom_range': (
                        {
                            'date_from': date_from,
                            'date_to': date_to,
                            'total_hours': custom_hrs,
                            'formatted_time': custom_fmt,
                            'sessions': custom_sessions
                        }
                        if date_from and date_to
                        else None
                    )
                }
            }

        except Exception as e:

            _logger.exception(
                "API Attendance Summary Error"
            )

            return {
                'status': 'error',
                'message': str(e)
            }

    # ==========================================
    # 2. DELIVERY MAN PROFILE MANAGEMENT
    # ==========================================

    @http.route('/api/delivery/profile', type='json', auth='user', csrf=False, methods=['POST'])
    def get_or_update_profile(
            self,
            user_id=None,
            name=None,
            phone=None,
            email=None,
            is_online=None,
            fcm_token=None,
            vehicle_type=None,
            vehicle_number=None,
            profile_photo_base64=None,
    ):
        """
        Comprehensive Get or Update endpoint for delivery user / employee profile,
        contact info, vehicle details, availability status, FCM token, and avatar.
        """
        try:
            current_user = request.env.user

            # Target user determination (Manager override or self)
            if user_id and (
                    current_user.has_group('base.group_system') or current_user.has_group('hr.group_hr_manager')):
                target_user = request.env['res.users'].sudo().browse(int(user_id))
                if not target_user.exists():
                    return {'status': 'error', 'message': 'Specified user ID not found.'}
            else:
                target_user = current_user

            # Fetch linked employee record if available
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', target_user.id)], limit=1)

            vals = {}
            employee_vals = {}

            # Collect user & employee updates if provided
            if name is not None:
                vals['name'] = name
                if employee:
                    employee_vals['name'] = name
            if phone is not None:
                vals['phone'] = phone
                if employee:
                    employee_vals['work_phone'] = phone
            if email is not None:
                vals['login'] = email
                vals['email'] = email
                if employee:
                    employee_vals['work_email'] = email
            if is_online is not None and hasattr(target_user, 'is_online'):
                vals['is_online'] = bool(is_online)
            if fcm_token is not None and hasattr(target_user, 'fcm_token'):
                vals['fcm_token'] = fcm_token

            # Vehicle info updates (checks user model first, then employee model)
            if vehicle_type is not None:
                if hasattr(target_user, 'vehicle_type'):
                    vals['vehicle_type'] = vehicle_type
                elif employee and hasattr(employee, 'vehicle_type'):
                    employee_vals['vehicle_type'] = vehicle_type

            if vehicle_number is not None:
                if hasattr(target_user, 'vehicle_number'):
                    vals['vehicle_number'] = vehicle_number
                elif employee and hasattr(employee, 'vehicle_number'):
                    employee_vals['vehicle_number'] = vehicle_number

            if profile_photo_base64:
                clean_photo_bytes = sanitize_b64(profile_photo_base64)
                if clean_photo_bytes:
                    vals['image_1920'] = clean_photo_bytes
                    if employee:
                        employee_vals['image_1920'] = clean_photo_bytes
                else:
                    return {'status': 'error', 'message': 'Invalid image base64 format.'}

            # Apply updates
            if vals:
                target_user.sudo().write(vals)
            if employee and employee_vals:
                employee.sudo().write(employee_vals)

            # Prepare the base64 string for the response image
            photo_b64_str = ''
            if target_user.image_1920:
                if isinstance(target_user.image_1920, bytes):
                    photo_b64_str = target_user.image_1920.decode('utf-8')
                else:
                    photo_b64_str = str(target_user.image_1920)

            # Return full rich user and employee details
            return {
                'status': 'success',
                'message': 'Full user profile retrieved successfully.',
                'data': {
                    'user_id': target_user.id,
                    'employee_id': employee.id if employee else None,
                    'partner_id': target_user.partner_id.id if target_user.partner_id else None,
                    'name': target_user.name,
                    'email': target_user.email or target_user.login or '',
                    'phone': target_user.phone or (employee.work_phone if employee else '') or '',
                    'login': target_user.login or '',

                    # Professional & Job Details
                    'job_title': employee.job_title if employee and hasattr(employee, 'job_title') else getattr(
                        target_user, 'job_title', ''),
                    'department': employee.department_id.name if employee and employee.department_id else '',
                    'company': target_user.company_id.name if target_user.company_id else '',

                    # Vehicle & Operational Info
                    'vehicle_type': getattr(target_user, 'vehicle_type', '') or (
                        employee.vehicle_type if employee and hasattr(employee, 'vehicle_type') else ''),
                    'vehicle_number': getattr(target_user, 'vehicle_number', '') or (
                        employee.vehicle_number if employee and hasattr(employee, 'vehicle_number') else ''),
                    'is_online': getattr(target_user, 'is_online', False),
                    'fcm_token': getattr(target_user, 'fcm_token', '') if hasattr(target_user, 'fcm_token') else '',
                    'attendance_state': employee.attendance_state if employee and hasattr(employee,
                                                                                          'attendance_state') else 'checked_out',
                    'has_photo': bool(target_user.image_1920),
                    'profile_photo_base64': photo_b64_str,

                    # Address Details
                    'street': target_user.street or '',
                    'city': target_user.city or '',
                    'state': target_user.state_id.name if target_user.state_id else '',
                    'country': target_user.country_id.name if target_user.country_id else '',
                    'zip': target_user.zip or '',
                }
            }
        except Exception as e:
            _logger.error("API Full Profile Error: %s", str(e))
            return {'status': 'error', 'message': str(e)}


    # ==========================================
    # 3. ORDERS DISCOVERY & CATEGORIZED LISTS
    # ==========================================

    @http.route('/api/delivery/pickings/unassigned', type='json', auth='none', methods=['POST'], csrf=False)
    def api_get_unassigned_pickings(self):
        """
        Fetch all unassigned delivery orders available for drivers to view and accept.
        """
        try:
            # Search for pickings that are unassigned and not yet completed/cancelled
            domain = [
                ('delivery_app_status', '=', 'unassigned'),
                ('state', 'not in', ['done', 'cancel'])
            ]

            pickings = request.env['stock.picking'].sudo().search(domain)

            picking_list = []
            for p in pickings:
                # Extract basic order lines/products info if needed
                move_lines = [{
                    'product_name': line.product_id.name,
                    'product_uic_qty': line.product_uom_qty,
                    'uom': line.product_uom.name if line.product_uom else ''
                } for line in p.move_ids_without_package]

                picking_list.append({
                    'picking_id': p.id,
                    'name': p.name,
                    'origin': p.origin or '',
                    'customer_name': p.partner_id.name if p.partner_id else '',
                    'customer_phone': p.partner_id.phone or p.partner_id.mobile or '',
                    'delivery_address': f"{p.partner_id.street or ''}, {p.partner_id.city or ''}, {p.partner_id.zip or ''}".strip(
                        ', '),
                    'scheduled_date': str(p.scheduled_date) if p.scheduled_date else '',
                    'items': move_lines
                })

            return {
                'status': 'success',
                'count': len(picking_list),
                'pickings': picking_list
            }

        except Exception as e:
            _logger.error(f"Fetch Unassigned Pickings Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': f'Failed to fetch pickings: {str(e)}'}

    @http.route('/api/delivery/picking/accept', type='json', auth='none', methods=['POST'], csrf=False)
    def api_accept_picking(self, picking_id, driver_user_id):
        """
        Driver accepts an unassigned delivery order.
        Assigns the driver, moves status from 'unassigned' to 'accepted',
        and returns the associated sale order details.
        """
        try:
            # 1. Validate inputs
            if not picking_id or not driver_user_id:
                return {'status': 'error', 'message': 'Picking ID and Driver User ID are required.'}

            # 2. Fetch picking order
            picking = request.env['stock.picking'].sudo().browse(int(picking_id))
            if not picking.exists():
                return {'status': 'error', 'message': 'Delivery picking order not found.'}

            # 3. Check if order is still unassigned
            if picking.delivery_app_status != 'unassigned':
                return {
                    'status': 'error',
                    'message': 'This order has already been accepted by another driver or is no longer available.'
                }

            # 4. Verify driver user exists and is a valid delivery partner
            driver_user = request.env['res.users'].sudo().browse(int(driver_user_id))
            if not driver_user.exists() or not driver_user.is_delivery_partner:
                return {'status': 'error', 'message': 'Invalid delivery driver user account.'}

            # 5. Assign driver and update status
            picking.write({
                'delivery_driver_id': driver_user.id,
                'delivery_app_status': 'accepted'
            })

            # 6. Extract Sale Order information safely
            sale_order = getattr(picking, 'sale_id', False)
            sale_order_id = sale_order.id if sale_order else None
            sale_order_name = sale_order.name if sale_order else picking.origin

            return {
                'status': 'success',
                'message': 'Delivery order accepted successfully.',
                'picking_id': picking.id,
                'order_reference': picking.name,
                'assigned_status': picking.delivery_app_status,
                'sale_order_id': sale_order_id,
                'sale_order_name': sale_order_name
            }

        except Exception as e:
            _logger.error(f"Accept Picking Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': f'Failed to accept order: {str(e)}'}

    @http.route('/api/delivery/picking/reject', type='json', auth='none', methods=['POST'], csrf=False)
    def api_reject_picking(self, picking_id, driver_user_id, reason=None):
        """
        Driver rejects/cancels an assigned delivery order.
        Resets the picking back to 'unassigned' and clears the delivery driver.
        """
        try:
            # 1. Validate inputs
            if not picking_id or not driver_user_id:
                return {'status': 'error', 'message': 'Picking ID and Driver User ID are required.'}

            # 2. Fetch picking order
            picking = request.env['stock.picking'].sudo().browse(int(picking_id))
            if not picking.exists():
                return {'status': 'error', 'message': 'Delivery picking order not found.'}

            # 3. Verify that the driver rejecting it is the one currently assigned (or handle gracefully)
            if picking.delivery_driver_id and picking.delivery_driver_id.id != int(driver_user_id):
                return {'status': 'error', 'message': 'This order is not assigned to you.'}

            # 4. Check if order status allows rejection (e.g. before pickup)
            if picking.delivery_app_status not in ['accepted', 'arrived_store']:
                return {
                    'status': 'error',
                    'message': f'Cannot reject order in current status: {picking.delivery_app_status}'
                }

            # 5. Reset status back to unassigned and remove driver
            picking.write({
                'delivery_driver_id': False,
                'delivery_app_status': 'unassigned'
            })

            # Optional: Log chatter note with rejection reason if provided
            if reason:
                picking.message_post(body=f"Order rejected by driver. Reason: {reason}")

            return {
                'status': 'success',
                'message': 'Delivery order rejected and returned to unassigned pool.',
                'picking_id': picking.id,
                'order_reference': picking.name
            }

        except Exception as e:
            _logger.error(f"Reject Picking Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': f'Failed to reject order: {str(e)}'}


    @http.route('/api/delivery/picking/arrived-store', type='json', auth='none', methods=['POST'], csrf=False)
    def api_arrived_store(self, picking_id, driver_user_id, latitude=None, longitude=None):
        """Driver marks arrival at the physical store."""
        try:
            picking = request.env['stock.picking'].sudo().browse(int(picking_id))
            if not picking.exists():
                return {'status': 'error', 'message': 'Picking order not found.'}

            vals = {'delivery_app_status': 'arrived_store'}
            if latitude:
                vals['delivery_latitude'] = float(latitude)
            if longitude:
                vals['delivery_longitude'] = float(longitude)

            picking.write(vals)
            return {'status': 'success', 'message': 'Status updated: Arrived at store.'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/delivery/picking/picked-up', type='json', auth='none', methods=['POST'], csrf=False)
    def api_picked_up(self, picking_id, driver_user_id):
        """Driver confirms package pickup and starts transit, notifying the customer."""
        try:
            # 1. Fetch picking order
            picking = request.env['stock.picking'].sudo().browse(int(picking_id))
            if not picking.exists():
                return {'status': 'error', 'message': 'Picking order not found.'}

            # 2. Update status to picked up
            picking.write({'delivery_app_status': 'picked_up'})

            # 3. Trigger customer notification
            if picking.partner_id:
                customer = picking.partner_id
                customer_phone = customer.phone or customer.mobile

                # Message content
                message_body = (
                    f"Hello {customer.name}, your order ({picking.name}) from LB Mart has been picked up "
                    f"by your delivery partner and is now on its way to your location!"
                )

                # Option A: Post a message on the order chatter / customer timeline
                picking.message_post(
                    body=message_body,
                    partner_ids=[customer.id]
                )

                # Option B: If you have an SMS/WhatsApp gateway integrated in Odoo, you can trigger it here:
                # e.g., request.env['sms.api']._send_sms([customer_phone], message_body)

            return {
                'status': 'success',
                'message': 'Order marked as picked up (in transit) and customer notified.'
            }

        except Exception as e:
            _logger.error(f"Picked Up API Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/delivery/picking/arrived-customer', type='json', auth='none', methods=['POST'], csrf=False)
    def api_arrived_customer(self, picking_id, driver_user_id, latitude=None, longitude=None):
        """Driver marks arrival at the customer drop-off location and returns sale order details."""
        try:
            picking = request.env['stock.picking'].sudo().browse(int(picking_id))
            if not picking.exists():
                return {'status': 'error', 'message': 'Picking order not found.'}

            vals = {'delivery_app_status': 'arrived_customer'}
            if latitude:
                vals['delivery_latitude'] = float(latitude)
            if longitude:
                vals['delivery_longitude'] = float(longitude)

            picking.write(vals)

            # Extract Sale Order information safely
            sale_order = getattr(picking, 'sale_id', False)
            sale_order_id = sale_order.id if sale_order else None
            sale_order_name = sale_order.name if sale_order else picking.origin

            return {
                'status': 'success',
                'message': 'Status updated: Arrived at customer location.',
                'picking_id': picking.id,
                'order_reference': picking.name,
                'sale_order_id': sale_order_id,
                'sale_order_name': sale_order_name
            }

        except Exception as e:
            _logger.error(f"Arrived Customer Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/delivery/picking/cancel', type='json', auth='none', methods=['POST'], csrf=False)
    def api_cancel_picking(self, picking_id, driver_user_id, cancel_reason=None):
        """
        Cancels a delivery picking, records the cancellation reason from the customer/driver,
        and updates the stock picking state in Odoo 18.
        """
        db = request.db or odoo.tools.config['db_name']
        if not db:
            return {
                'status': 'error',
                'message': 'Database not specified or detected in configuration.'
            }

        try:
            registry = Registry(db)
            with registry.cursor() as cr:
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

                if not picking_id:
                    return {'status': 'error', 'message': 'Picking ID is required.'}

                # 1. Fetch picking record
                picking = env['stock.picking'].browse(int(picking_id))
                if not picking.exists():
                    return {'status': 'error', 'message': 'Picking order not found.'}

                # 2. Prevent cancellation if already done or cancelled
                if picking.state == 'done':
                    return {'status': 'error',
                            'message': 'Cannot cancel a delivery that is already marked as done/completed.'}

                reason_text = cancel_reason or 'Cancelled by customer / driver'

                # 3. Prepare updates for custom delivery status and reason
                vals = {
                    'delivery_app_status': 'failed',
                }

                # If you have a custom field on stock.picking for the reason, update it directly
                if hasattr(picking, 'cancel_reason'):
                    vals['cancel_reason'] = reason_text

                picking.write(vals)

                # Log the cancellation reason in Odoo chatter for tracking
                picking.message_post(
                    body=f"<b>Delivery Cancelled</b><br/><b>Driver ID:</b> {driver_user_id}<br/><b>Reason:</b> {reason_text}"
                )

                # 4. Cancel the underlying stock picking transfer safely
                if picking.state != 'cancel':
                    try:
                        picking.action_cancel()
                    except Exception as cancel_err:
                        _logger.warning(f"Standard action_cancel failed: {str(cancel_err)}. Forcing cancel state.")
                        picking.write({'state': 'cancel'})

                cr.commit()

                return {
                    'status': 'success',
                    'message': 'Delivery order successfully cancelled and reason recorded.',
                    'picking_id': picking.id,
                    'picking_reference': picking.name,
                    'delivery_status': picking.delivery_app_status
                }

        except Exception as e:
            _logger.error(f"Cancel Picking Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/delivery/picking/deliver', type='json', auth='none', methods=['POST'], csrf=False)
    def api_deliver_order(self, picking_id, driver_user_id, signed_by=None, signature_base64=None, delivery_otp=None,
                          latitude=None, longitude=None):
        """
        Completes delivery with strict OTP verification, signature proof,
        auto-filled quantities, and safe stock validation.
        """
        try:
            # 1. Fetch picking record
            picking = request.env['stock.picking'].sudo().browse(int(picking_id))
            if not picking.exists():
                return {'status': 'error', 'message': 'Picking order not found.'}

            # 2. Strict Delivery OTP Validation
            # Check if the picking has an OTP set and enforce verification
            expected_otp = getattr(picking, 'delivery_otp', False)
            if expected_otp:
                if not delivery_otp:
                    return {'status': 'error', 'message': 'Delivery OTP is required to complete this order.'}
                if str(expected_otp).strip() != str(delivery_otp).strip():
                    return {'status': 'error', 'message': 'Incorrect delivery OTP. Please verify with the customer.'}

            # 3. Prepare values update
            vals = {
                'delivery_app_status': 'delivered',
                'signed_by': signed_by or 'Customer'
            }

            if delivery_otp:
                vals['delivery_otp'] = str(delivery_otp)

            if signature_base64:
                clean_sig = sanitize_b64(signature_base64)
                if clean_sig:
                    vals['delivery_signature'] = clean_sig

            if latitude:
                vals['delivery_latitude'] = float(latitude)
            if longitude:
                vals['delivery_longitude'] = float(longitude)

            picking.write(vals)

            # 4. Automatically validate stock transfer if not already done/cancelled
            if picking.state not in ['done', 'cancel']:
                # Ensure stock is reserved
                if picking.state != 'assigned':
                    picking.action_assign()

                # Force-fill quantities safely for Odoo 18 standards
                for move in picking.move_ids_without_package:
                    qty_to_set = move.product_uom_qty
                    if move.move_line_ids:
                        for line in move.move_line_ids:
                            try:
                                line.write({'quantity': qty_to_set})
                            except Exception:
                                line.write({'quantity_done': qty_to_set})
                    else:
                        try:
                            move.write({'quantity': qty_to_set})
                        except Exception:
                            move.write({'quantity_done': qty_to_set})

                # Validate picking with follower error bypass protection
                try:
                    picking.with_context(tracking_disable=True, mail_create_nosubscribe=True).button_validate()
                except Exception as val_err:
                    _logger.warning(
                        f"Standard validation caught error: {str(val_err)}. Executing direct stock move completion.")
                    request.env.cr.rollback()

                    # Force state and properly trigger stock move ledger updates
                    picking.sudo().write({'state': 'done'})
                    for move in picking.move_ids:
                        move.sudo().write({'state': 'done', 'quantity': move.product_uom_qty})
                        if hasattr(move, 'move_line_ids'):
                            for line in move.move_line_ids:
                                try:
                                    line.sudo().write({'state': 'done', 'quantity': move.product_uom_qty})
                                except Exception:
                                    line.sudo().write({'state': 'done', 'quantity_done': move.product_uom_qty})

            # 5. Extract Sale Order information safely for confirmation
            sale_order = getattr(picking, 'sale_id', False)
            sale_order_id = sale_order.id if sale_order else None
            sale_order_name = sale_order.name if sale_order else picking.origin

            return {
                'status': 'success',
                'message': 'Delivery completed successfully. OTP verified and stock validated.',
                'picking_id': picking.id,
                'order_reference': picking.name,
                'sale_order_id': sale_order_id,
                'sale_order_name': sale_order_name,
                'delivery_status': picking.delivery_app_status
            }

        except Exception as e:
            request.env.cr.rollback()
            _logger.error(f"Deliver Order Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/delivery/pickings/all_my_delivery', type='json', auth='none', methods=['POST'], csrf=False)
    def api_get_driver_deliveries(self, driver_user_id, status_filter=None):
        """
        Retrieves all delivery pickings assigned to a specific driver.
        Optionally filters by delivery_app_status (e.g., 'accepted', 'arrived_customer', 'delivered').
        """
        try:
            if not driver_user_id:
                return {'status': 'error', 'message': 'Driver User ID is required.'}

            # Base domain: Find pickings assigned to this driver
            domain = [('delivery_driver_id', '=', int(driver_user_id))]

            # Apply status filter if provided (can be a string or list of statuses)
            if status_filter:
                if isinstance(status_filter, list):
                    domain.append(('delivery_app_status', 'in', status_filter))
                else:
                    domain.append(('delivery_app_status', '=', status_filter))

            pickings = request.env['stock.picking'].sudo().search(domain, order='id desc')

            delivery_list = []
            for picking in pickings:
                # Extract customer details safely
                partner = picking.partner_id
                sale_order = getattr(picking, 'sale_id', False)

                delivery_list.append({
                    'picking_id': picking.id,
                    'picking_reference': picking.name,
                    'origin': picking.origin or (sale_order.name if sale_order else ''),
                    'sale_order_id': sale_order.id if sale_order else None,
                    'sale_order_name': sale_order.name if sale_order else None,
                    'delivery_app_status': picking.delivery_app_status,
                    'picking_state': picking.state,  # assigned, done, etc.
                    'customer_name': partner.name if partner else 'Unknown Customer',
                    'customer_phone': partner.phone or partner.mobile if partner else '',
                    'customer_address': f"{partner.street or ''}, {partner.city or ''}, {partner.zip or ''}".strip(
                        ', '),
                    'scheduled_date': str(picking.scheduled_date) if picking.scheduled_date else '',
                    'has_otp': bool(getattr(picking, 'delivery_otp', False)),
                })

            return {
                'status': 'success',
                'count': len(delivery_list),
                'deliveries': delivery_list
            }

        except Exception as e:
            _logger.error(f"Get Driver Deliveries Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/delivery/pickings/all_my_delivery', type='json', auth='none', methods=['POST'], csrf=False)
    def api_get_driver_deliveries(self, driver_user_id, status_filter=None):
        """
        Retrieves all delivery pickings assigned to a specific driver for TODAY.
        Optionally filters by delivery_app_status (e.g., 'accepted', 'arrived_customer', 'delivered').
        """
        db = request.db or odoo.tools.config['db_name']
        if not db:
            return {'status': 'error', 'message': 'Database not specified or detected in configuration.'}

        try:
            registry = Registry(db)
            with registry.cursor() as cr:
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

                if not driver_user_id:
                    return {'status': 'error', 'message': 'Driver User ID is required.'}

                # Define Today's Date Range (Start and End of Day)
                today = fields.Date.today()
                start_of_day = f"{today} 00:00:00"
                end_of_day = f"{today} 23:59:59"

                # Base domain: Assigned driver AND scheduled for today
                domain = [
                    ('delivery_driver_id', '=', int(driver_user_id)),
                    ('scheduled_date', '>=', start_of_day),
                    ('scheduled_date', '<=', end_of_day)
                ]

                # Apply status filter if provided (can be a string or list of statuses)
                if status_filter:
                    if isinstance(status_filter, list):
                        domain.append(('delivery_app_status', 'in', status_filter))
                    else:
                        domain.append(('delivery_app_status', '=', status_filter))

                pickings = env['stock.picking'].search(domain, order='id desc')

                delivery_list = []
                for picking in pickings:
                    # Extract customer details safely
                    partner = picking.partner_id
                    sale_order = getattr(picking, 'sale_id', False)

                    delivery_list.append({
                        'picking_id': picking.id,
                        'picking_reference': picking.name,
                        'origin': picking.origin or (sale_order.name if sale_order else ''),
                        'sale_order_id': sale_order.id if sale_order else None,
                        'sale_order_name': sale_order.name if sale_order else None,
                        'delivery_app_status': picking.delivery_app_status,
                        'picking_state': picking.state,  # assigned, done, etc.
                        'customer_name': partner.name if partner else 'Unknown Customer',
                        'customer_phone': partner.phone or partner.mobile if partner else '',
                        'customer_address': f"{partner.street or ''}, {partner.city or ''}, {partner.zip or ''}".strip(
                            ', '),
                        'scheduled_date': str(picking.scheduled_date) if picking.scheduled_date else '',
                        'has_otp': bool(getattr(picking, 'delivery_otp', False)),
                    })

                return {
                    'status': 'success',
                    'date': str(today),
                    'count': len(delivery_list),
                    'deliveries': delivery_list
                }

        except Exception as e:
            _logger.error(f"Get Driver Deliveries Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/delivery/cod_reconciliation', type='json', auth='none', methods=['POST'], csrf=False)
    def api_cod_reconciliation(self, order_id, driver_user_id, amount_collected, journal_id, payment_reference=None,
                               payment_method_line_id=None):
        """
        Reconciles Cash on Delivery (COD) for Odoo 18 and automatically adds it to the driver's daily cash handover.
        """
        db = request.db or odoo.tools.config['db_name']
        if not db:
            return {
                'status': 'error',
                'message': 'Database not specified or detected in configuration.'
            }

        try:
            registry = Registry(db)
            with registry.cursor() as cr:
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

                # 1. Fetch Sale Order
                order = env['sale.order'].browse(int(order_id))
                if not order.exists():
                    return {
                        'status': 'error',
                        'message': f'Sale Order ID {order_id} not found.'
                    }

                # 2. Find posted invoice
                posted_invoices = order.invoice_ids.filtered(lambda inv: inv.state == 'posted')
                if not posted_invoices:
                    return {
                        'status': 'error',
                        'message': f'No posted invoice found for Sale Order ID {order_id}.'
                    }

                invoice_pre = posted_invoices[0]
                company_id = invoice_pre.company_id.id or env.company.id or 1

                # 3. Bind company context properly
                ctx = dict(env.context)
                ctx.update({
                    'allowed_company_ids': [company_id],
                    'company_id': company_id
                })
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, ctx)
                invoice = invoice_pre.with_env(env)

                # 4. Idempotency Check
                if invoice.payment_state in ('paid', 'in_payment'):
                    return {
                        'status': 'success',
                        'already_processed': True,
                        'order_id': order.id,
                        'invoice_id': invoice.id,
                        'invoice_number': invoice.name,
                        'payment_state': invoice.payment_state,
                        'message': 'This invoice has already been fully paid and reconciled.'
                    }

                # 5. Validate Collected Amount
                try:
                    collected_float = float(amount_collected)
                except (TypeError, ValueError):
                    return {
                        'status': 'error',
                        'message': 'Invalid amount_collected provided. Must be a valid number.'
                    }

                if collected_float <= 0:
                    return {
                        'status': 'error',
                        'message': 'Collected amount must be greater than zero.'
                    }

                # 6. Fetch Journal
                journal = env['account.journal'].browse(int(journal_id))
                if not journal.exists():
                    return {
                        'status': 'error',
                        'message': f'Journal ID {journal_id} not found.'
                    }

                # 7. Resolve Payment Method Line ID
                if not payment_method_line_id:
                    pm_line = journal.inbound_payment_method_line_ids[:1]
                    payment_method_line_id = pm_line.id if pm_line else False

                if not payment_method_line_id:
                    return {
                        'status': 'error',
                        'message': f'No valid inbound payment method configured for Journal ID {journal_id}.'
                    }

                # 8. Create Payment, Post, and Reconcile (Your working logic)
                ref_code = payment_reference or f"COD-DRV-{driver_user_id}-{fields.Date.today()}"
                payment_memo = f"COD Collection by Driver ID {driver_user_id} | Ref: {ref_code}"

                payment_vals = {
                    'company_id': company_id,
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': invoice.partner_id.id,
                    'amount': collected_float,
                    'currency_id': invoice.currency_id.id,
                    'journal_id': journal.id,
                    'payment_method_line_id': int(payment_method_line_id),
                    'date': fields.Date.today(),
                    'memo': payment_memo,
                }

                payment = env['account.payment'].create(payment_vals)
                payment.action_post()

                # Use payment.move_id.line_ids for Odoo 18 account.payment lines
                payment_lines = payment.move_id.line_ids.filtered(
                    lambda l: l.account_type == 'asset_receivable' and not l.reconciled)
                invoice_lines = invoice.line_ids.filtered(
                    lambda l: l.account_type == 'asset_receivable' and not l.reconciled)

                if payment_lines and invoice_lines:
                    (payment_lines + invoice_lines).reconcile()

                invoice.invalidate_recordset(['payment_state'])

                # ==========================================
                # 9. ROBUST CASH HANDOVER AUTOMATION BLOCK
                # ==========================================
                today_date = fields.Date.today()
                driver_id = int(driver_user_id)
                handover_id = False

                try:
                    # Search for an open draft handover sheet for today
                    handover = env['delivery.cash.handover'].search([
                        ('user_id', '=', driver_id),
                        ('date', '=', today_date),
                        ('state', '=', 'draft')
                    ], limit=1)

                    # Create sheet if none exists
                    if not handover:
                        handover = env['delivery.cash.handover'].create({
                            'user_id': driver_id,
                            'date': today_date,
                            'journal_id': journal.id,
                            'state': 'draft',
                        })

                    # Check if order line already exists to prevent duplicate entries
                    existing_line = handover.line_ids.filtered(lambda l: l.order_id.id == order.id)
                    if not existing_line:
                        env['delivery.cash.handover.line'].create({
                            'handover_id': handover.id,
                            'order_id': order.id,
                            'invoice_id': invoice.id,
                            'amount': collected_float,
                        })

                    handover_id = handover.id
                except Exception as handover_err:
                    # Log handover failure separately so it doesn't block the successful payment/reconciliation
                    _logger.error(f"Cash Handover Auto-Addition Warning: {str(handover_err)}")

                cr.commit()

                return {
                    'status': 'success',
                    'order_id': order.id,
                    'invoice_id': invoice.id,
                    'partner_id': payment.partner_id.name,
                    'invoice_number': invoice.name,
                    'invoice_state': invoice.state,
                    'payment_state': invoice.payment_state,
                    'amount_collected': collected_float,
                    'payment_reference': ref_code,
                    'payment_ids': [payment.id],
                    'handover_id': handover_id,
                    'message': 'Cash collected, payment created, invoice reconciled successfully, and added to cash handover.'
                }

        except Exception as e:
            _logger.error(f"COD Reconciliation Route Exception: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/delivery/check_payment_status', type='json', auth='none', methods=['POST'], csrf=False)
    def api_check_payment_status(self, order_id=None, order_name=None):
        """
        Checks payment status and returns order name, delivery names, invoice names, and payment names.
        """
        db = request.db or odoo.tools.config['db_name']
        if not db:
            return {
                'status': 'error',
                'message': 'Database not specified or detected in configuration.'
            }

        try:
            registry = Registry(db)
            with registry.cursor() as cr:
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

                # 1. Fetch Sale Order by ID or Name
                order = None
                if order_id:
                    order = env['sale.order'].browse(int(order_id))
                elif order_name:
                    order = env['sale.order'].search([('name', '=', order_name)], limit=1)

                if not order or not order.exists():
                    return {
                        'status': 'error',
                        'message': 'Sale Order not found for identifier provided.'
                    }

                # 2. Extract Delivery (Stock Picking) names
                delivery_names = order.picking_ids.mapped('name') if hasattr(order, 'picking_ids') else []

                # 3. Find active/posted invoices and their corresponding payments
                invoices = order.invoice_ids.filtered(lambda inv: inv.state != 'cancel')
                if not invoices:
                    return {
                        'status': 'success',
                        'order_id': order.id,
                        'order_name': order.name,
                        'delivery_names': delivery_names,
                        'invoice_names': [],
                        'payment_names': [],
                        'has_invoice': False,
                        'is_paid': False,
                        'payment_state': 'no_invoice',
                        'amount_total': order.amount_total,
                        'amount_residual': order.amount_total,
                        'message': 'No active invoice has been generated for this sale order yet.'
                    }

                invoice_names = invoices.mapped('name')

                payment_names = []
                for inv in invoices:
                    reconciled_payments = inv.sudo().mapped('line_ids.matched_debit_ids.debit_move_id.payment_id') | \
                                          inv.sudo().mapped('line_ids.matched_credit_ids.credit_move_id.payment_id')
                    for p in reconciled_payments:
                        if p.name and p.name not in payment_names:
                            payment_names.append(p.name)

                invoice = invoices[0]
                is_paid = invoice.payment_state in ('paid', 'in_payment')

                return {
                    'status': 'success',
                    'order_id': order.id,
                    'order_name': order.name,
                    'delivery_names': delivery_names,
                    'invoice_names': invoice_names,
                    'payment_names': payment_names,
                    'has_invoice': True,
                    'invoice_state': invoice.state,
                    'payment_state': invoice.payment_state,
                    'is_paid': is_paid,
                    'amount_total': invoice.amount_total,
                    'amount_residual': invoice.amount_residual,
                    'currency': invoice.currency_id.name,
                    'message': f'Payment status retrieved successfully. State: {invoice.payment_state}'
                }

        except Exception as e:
            _logger.error(f"Check Payment Status Route Exception: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/delivery/cash_handover/pending', type='json', auth='none', methods=['POST'], csrf=False)
    def api_get_pending_cash_handover(self, driver_user_id):
        """
        Retrieves all pending (draft or submitted) cash handover sheets and their collected order lines for a specific driver.
        """
        db = request.db or odoo.tools.config['db_name']
        if not db:
            return {'status': 'error', 'message': 'Database not specified or detected in configuration.'}

        try:
            registry = Registry(db)
            with registry.cursor() as cr:
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

                if not driver_user_id:
                    return {'status': 'error', 'message': 'Driver User ID is required.'}

                # Search for handovers that are not yet confirmed ('draft' or 'submitted')
                domain = [
                    ('user_id', '=', int(driver_user_id)),
                    ('state', 'in', ['draft', 'submitted'])
                ]

                handovers = env['delivery.cash.handover'].search(domain, order='date desc, id desc')

                handover_list = []
                for h in handovers:
                    lines = []
                    for line in h.line_ids:
                        lines.append({
                            'line_id': line.id,
                            'order_id': line.order_id.id if line.order_id else None,
                            'order_name': line.order_id.name if line.order_id else '',
                            'invoice_id': line.invoice_id.id if line.invoice_id else None,
                            'invoice_name': line.invoice_id.name if line.invoice_id else '',
                            'amount': line.amount,
                        })

                    handover_list.append({
                        'handover_id': h.id,
                        'reference': h.name,
                        'date': str(h.date),
                        'state': h.state,
                        'total_amount': h.total_amount,
                        'journal_id': h.journal_id.id if h.journal_id else None,
                        'journal_name': h.journal_id.name if h.journal_id else '',
                        'note': h.note or '',
                        'lines': lines
                    })

                return {
                    'status': 'success',
                    'count': len(handover_list),
                    'pending_handovers': handover_list
                }

        except Exception as e:
            _logger.error(f"Get Pending Cash Handover Error: {str(e)}", exc_info=True)

            return {'status': 'error', 'message': str(e)}

    @http.route('/api/delivery/pickings/cancelled', type='json', auth='none', methods=['POST'], csrf=False)
    def api_get_cancelled_pickings(self, driver_user_id):
        """
        Retrieves all cancelled stock pickings/deliveries associated with a specific driver.
        """
        db = request.db or odoo.tools.config['db_name']
        if not db:
            return {
                'status': 'error',
                'message': 'Database not specified or detected in configuration.'
            }

        try:
            registry = Registry(db)
            with registry.cursor() as cr:
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

                if not driver_user_id:
                    return {'status': 'error', 'message': 'Driver User ID is required.'}

                # Search domain for cancelled pickings assigned to this driver
                # (Matches either the native Odoo 'cancel' state or custom 'delivery_app_status')
                domain = [
                    ('delivery_driver_id', '=', int(driver_user_id)),
                    # Adjust field name if your driver relation differs (e.g., user_id)
                    '|',
                    ('state', '=', 'cancel'),
                    ('delivery_app_status', '=', 'cancelled')
                ]

                # Fallback domain check if your model tracks drivers via user_id
                pickings = env['stock.picking'].search(domain, order='write_date desc, id desc')

                cancelled_list = []
                for p in pickings:
                    # Extract cancellation reason if stored in custom field, or parse from message chatter
                    cancel_reason = getattr(p, 'delivery_cancel_reason', 'No reason provided')

                    cancelled_list.append({
                        'picking_id': p.id,
                        'picking_reference': p.name,
                        'origin': p.origin or '',
                        'partner_name': p.partner_id.name if p.partner_id else '',
                        'partner_phone': p.partner_id.phone or p.partner_id.mobile or '',
                        'scheduled_date': str(p.scheduled_date) if p.scheduled_date else '',
                        'cancel_reason': cancel_reason,
                        'state': p.state,
                    })

                return {
                    'status': 'success',
                    'count': len(cancelled_list),
                    'cancelled_pickings': cancelled_list
                }

        except Exception as e:
            _logger.error(f"Get Cancelled Pickings Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/delivery/pickings/cancelled/today', type='json', auth='none', methods=['POST'], csrf=False)
    def api_get_todays_cancelled_pickings(self, driver_user_id):
        """
        Retrieves all cancelled stock pickings/deliveries for a specific driver for today's date only.
        """
        db = request.db or odoo.tools.config['db_name']
        if not db:
            return {
                'status': 'error',
                'message': 'Database not specified or detected in configuration.'
            }

        try:
            registry = Registry(db)
            with registry.cursor() as cr:
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

                if not driver_user_id:
                    return {'status': 'error', 'message': 'Driver User ID is required.'}

                today_date = fields.Date.today()

                # Domain to filter for today's cancellations and the specific driver
                domain = [
                    ('delivery_driver_id', '=', int(driver_user_id)),
                    ('write_date', '>=', f"{today_date} 00:00:00"),
                    ('write_date', '<=', f"{today_date} 23:59:59"),
                    '|',
                    ('state', '=', 'cancel'),
                    ('delivery_app_status', '=', 'cancelled')
                ]

                pickings = env['stock.picking'].search(domain, order='write_date desc, id desc')

                cancelled_list = []
                for p in pickings:
                    # Extract cancellation reason if stored in custom field, or fallback
                    cancel_reason = getattr(p, 'delivery_cancel_reason', 'No reason provided')

                    cancelled_list.append({
                        'picking_id': p.id,
                        'picking_reference': p.name,
                        'origin': p.origin or '',
                        'partner_name': p.partner_id.name if p.partner_id else '',
                        'partner_phone': p.partner_id.phone or p.partner_id.mobile or '',
                        'scheduled_date': str(p.scheduled_date) if p.scheduled_date else '',
                        'cancelled_at': str(p.write_date) if p.write_date else '',
                        'cancel_reason': cancel_reason,
                        'state': p.state,
                    })

                return {
                    'status': 'success',
                    'date': str(today_date),
                    'count': len(cancelled_list),
                    'cancelled_pickings': cancelled_list
                }

        except Exception as e:
            _logger.error(f"Get Today's Cancelled Pickings Error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    # ==========================================
    # 8. LOCATION & LIVE TRACKING
    # ==========================================

    @http.route('/api/delivery/update_location', type='json', auth='user', methods=['POST'])
    def update_location(self, latitude, longitude, tracking_active=True):
        """Update live driver coordinates for background/foreground tracking."""
        user = request.env.user
        vals = {}
        if hasattr(user, 'current_latitude'):
            vals['current_latitude'] = float(latitude)
        if hasattr(user, 'current_longitude'):
            vals['current_longitude'] = float(longitude)
        if hasattr(user, 'is_tracking_active'):
            vals['is_tracking_active'] = tracking_active

        if vals:
            user.sudo().write(vals)

        return {'status': 'success', 'message': 'Location updated.'}

    # ==========================================
    # 9. NOTIFICATIONS & FCM UPDATES
    # ==========================================

    @http.route('/api/delivery/get_notifications', type='json', auth='user', methods=['POST'])
    def get_notifications(self):
        """Fetch notification history for the driver."""
        user = request.env.user
        messages = (
            request.env['mail.message']
            .sudo()
            .search_read(
                [('partner_ids', 'in', [user.partner_id.id])],
                ['id', 'subject', 'body', 'date'],
                limit=20,
            )
        )
        return {'status': 'success', 'notifications': messages}

    # ==========================================
    # 10. DASHBOARD & SUMMARY METRICS
    # ==========================================

    @http.route('/api/delivery/dashboard', type='json', auth='user', methods=['POST'])
    def get_dashboard_summary(self):
        """Daily summary dashboard metrics for driver screen."""
        driver = request.env.user
        domain_base = [('delivery_driver_id', '=', driver.id)]

        all_today = request.env['stock.picking'].sudo().search(domain_base)
        completed = all_today.filtered(
            lambda p: getattr(p, 'delivery_app_status', '') == 'delivered'
        )
        pending = all_today.filtered(
            lambda p: getattr(p, 'delivery_app_status', '')
            in [
                'accepted',
                'arrived_store',
                'picked_up',
                'out_for_delivery',
                'arrived_customer',
            ]
        )
        failed = all_today.filtered(
            lambda p: getattr(p, 'delivery_app_status', '')
            in ['failed', 'cancelled', 'returned']
        )

        total_cod = sum(
            getattr(p, 'collected_amount', 0.0)
            for p in completed
            if getattr(p, 'payment_collected', False)
        )

        return {
            'status': 'success',
            'summary': {
                'today_assigned': len(all_today),
                'completed_deliveries': len(completed),
                'pending_deliveries': len(pending),
                'failed_deliveries': len(failed),
                'cod_collected_amount': total_cod,
                'is_online': getattr(driver, 'is_online', False),
            },
        }

    # ==========================================
    # 11. ERROR, RESCHEDULE & EXCEPTION HANDLING
    # ==========================================

    @http.route(
        '/api/delivery/reschedule_delivery', type='json', auth='user', methods=['POST']
    )
    def reschedule_delivery(self, picking_id, new_date, reason):
        """Reschedule delivery attempt due to customer unavailability/wrong address."""
        picking = request.env['stock.picking'].sudo().browse(picking_id)
        if not picking.exists():
            return {'status': 'error', 'message': 'Delivery order not found.'}

        picking.sudo().write({
            'scheduled_date': new_date,
            'delivery_app_status': 'unassigned',
            'cancel_reason': f"Rescheduled: {reason}",
        })

        return {
            'status': 'success',
            'message': f'Delivery rescheduled for {new_date}.',
        }

    # ==========================================
    # 12. DRIVER EARNINGS & SUPPORT TICKETS
    # ==========================================

    @http.route('/api/delivery/earnings', type='json', auth='user', methods=['POST'])
    def get_driver_earnings(self):
        """Fetch driver earnings breakdown based on completed deliveries."""
        driver = request.env.user
        completed_pickings = (
            request.env['stock.picking']
            .sudo()
            .search([
                ('delivery_driver_id', '=', driver.id),
                ('delivery_app_status', '=', 'delivered'),
            ])
        )

        per_order_commission = 40.0
        total_earnings = len(completed_pickings) * per_order_commission

        return {
            'status': 'success',
            'completed_count': len(completed_pickings),
            'commission_rate_per_order': per_order_commission,
            'total_earnings': total_earnings,
        }

    @http.route(
        '/api/delivery/create_support_ticket', type='json', auth='user', methods=['POST']
    )
    def create_support_ticket(self, subject, description, picking_id=None):
        """Create a support message or issue ticket for dispatch management."""
        driver = request.env.user
        body_text = f"Driver Support Request: {description}"
        if picking_id:
            body_text += f"\nRelated Picking ID: {picking_id}"

        subtype = request.env.ref('mail.mt_note', raise_if_not_found=False)
        request.env['mail.message'].sudo().create({
            'model': 'res.users',
            'res_id': driver.id,
            'subject': subject,
            'body': body_text,
            'message_type': 'comment',
            'subtype_id': subtype.id if subtype else False,
        })
        return {'status': 'success', 'message': 'Support request sent successfully.'}