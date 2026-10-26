import random
import logging
import threading
import requests
from datetime import datetime, timedelta
from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SignupTempUser(models.Model):
    _name = 'signup.temp.user'
    _description = 'Temporary Signup Staging for OTP Verification'

    name = fields.Char(string='Name', required=True)
    login = fields.Char(string='Email (Login)', required=True)
    phone = fields.Char(string='Mobile/WhatsApp Number', required=True)
    password = fields.Char(string='Encrypted/Plain Password', required=True)

    email_otp = fields.Char(string='Email OTP', readonly=True)
    whatsapp_otp = fields.Char(string='WhatsApp OTP', readonly=True)

    otp_expiry = fields.Datetime(string='OTP Expiry Time', readonly=True)
    is_verified = fields.Boolean(string='Verified', default=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Automatically generate and send OTPs upon creating a temp signup record."""
        records = super(SignupTempUser, self).create(vals_list)
        for record in records:
            record.generate_otps()
        return records

    def generate_otps(self):
        """Generates 6-digit OTPs and sets a 10-minute validity window."""
        self.ensure_one()
        self.email_otp = "".join(random.choices("0123456789", k=6))
        self.whatsapp_otp = "".join(random.choices("0123456789", k=6))
        self.otp_expiry = datetime.now() + timedelta(minutes=10)

        # Trigger sending mechanisms automatically
        self._send_email_otp()
        self._send_whatsapp_otp()

    def _send_email_otp(self):
        """Send Email OTP via Odoo Mail engine with robust sender fallback."""
        self.ensure_one()
        try:
            # Fetch default outgoing mail configuration sender or system email
            icp = self.env['ir.config_parameter'].sudo()
            company = self.env.company

            # Fallback chain for sender email address
            email_from = (
                    company.email
                    or icp.get_param('mail.catchall.domain')
                    or icp.get_param('web.base.url')
            )

            # If still looking like a URL, fallback to a standard admin/default address
            if not email_from or '@' not in email_from:
                email_from = self.env.user.email or 'noreply@example.com'

            mail_values = {
                'subject': 'Your Signup Verification OTP',
                'email_from': email_from,
                'email_to': self.login,
                'body_html': f"""
                    <div style="font-family: Arial, sans-serif; padding: 20px;">
                        <h2>Hello {self.name},</h2>
                        <p>Thank you for signing up. Your email verification OTP code is:</p>
                        <h1 style="color: #4CAF50; letter-spacing: 2px;">{self.email_otp}</h1>
                        <p>This code is valid for 10 minutes.</p>
                    </div>
                """,
            }

            # Create and immediately send
            mail = self.env['mail.mail'].sudo().create(mail_values)
            mail.send(raise_exception=True)  # raise_exception=True forces Odoo to log the exact SMTP/Mail Server error
            _logger.info(f"Email OTP successfully sent to {self.login}")

        except Exception as e:
            _logger.error(f"Failed to send Email OTP to {self.login}: {str(e)}")

    def _send_whatsapp_otp(self):
        """Send WhatsApp OTP via Meta Cloud API using background threading, active config, and retry logic."""
        self.ensure_one()
        db_name = self.env.cr.dbname
        raw_phone = self.phone

        if not raw_phone:
            _logger.warning(f"WhatsApp OTP Skipped: No phone number for temp user {self.login}")
            return False

        # Clean phone number (Digits only, add 91 country code if 10 digits)
        cleaned_phone = "".join(filter(str.isdigit, str(raw_phone)))
        if len(cleaned_phone) == 10:
            cleaned_phone = f"91{cleaned_phone}"

        otp_code = str(self.whatsapp_otp)
        user_name = str(self.name or "User").strip()

        whatsapp_config = self.env['whatsapp.config'].get_active_config()
        if not whatsapp_config:
            _logger.warning("WhatsApp Notification Skipped: No active 'whatsapp.config' record found.")
            return False

        phone_number_id = whatsapp_config['phone_number_id']
        access_token = whatsapp_config['access_token']
        api_version = whatsapp_config.get('api_version', 'v25.0')

        # Template parameters matching your approved Meta template body variables
        parameters = [
            {"type": "text", "text": otp_code}
        ]

        def _async_send():
            from odoo.modules.registry import Registry
            import time

            registry = Registry(db_name)
            with registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": cleaned_phone,
                    "type": "template",
                    "template": {
                        "name": "lbmart_signup_otp",
                        "language": {"code": "en"},
                        "components": [
                            {
                                "type": "body",
                                "parameters": parameters
                            }
                        ]
                    }
                }

                # Retry logic: Try up to 3 times if network timeout occurs
                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    try:
                        # Increased timeout to 35 seconds
                        response = requests.post(url, headers=headers, json=payload, timeout=35)
                        if response.status_code in [200, 201]:
                            _logger.info(f"WhatsApp OTP sent successfully to {cleaned_phone}")
                            return
                        else:
                            _logger.error(f"WhatsApp API Error [{response.status_code}]: {response.text}")
                            _logger.error(f"Failed Payload: {payload}")
                            break  # Don't retry on client/server API errors (like bad tokens or template errors)
                    except requests.exceptions.Timeout:
                        _logger.warning(f"WhatsApp API Timeout (Attempt {attempt}/{max_retries}) for {cleaned_phone}")
                        if attempt == max_retries:
                            _logger.error("WhatsApp API failed after maximum retry attempts due to timeouts.")
                        else:
                            time.sleep(2)  # Wait 2 seconds before retrying
                    except Exception as e:
                        _logger.error(f"Failed to execute background WhatsApp API call for OTP: {str(e)}")
                        break

        thread = threading.Thread(target=_async_send)
        thread.daemon = True
        thread.start()
        return True

    def verify_and_create_user(self, e_otp, w_otp):
        """Validates OTPs and provisions the actual res.users record."""
        self.ensure_one()
        if datetime.now() > fields.Datetime.from_string(self.otp_expiry):
            raise UserError(_("The OTP has expired. Please request a new one."))

        if self.email_otp != e_otp or self.whatsapp_otp != w_otp:
            raise UserError(_("Invalid Email or WhatsApp OTP code provided."))

        # OTPs are correct: Proceed to create real Odoo User safely
        user_vals = {
            'name': self.name,
            'login': self.login,
            'email': self.login,
            'phone': self.phone,
            'password': self.password,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]  # Default to portal/customer
        }
        real_user = self.env['res.users'].sudo().create(user_vals)

        self.is_verified = True
        return real_user