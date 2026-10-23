from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo import models, fields, api
import logging
import requests
import threading
_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    delivery_driver_id = fields.Many2one(
        'res.users',
        string='Assigned Delivery Partner',
        domain="[('is_delivery_partner', '=', True)]",
        tracking=True
    )

    delivery_app_status = fields.Selection([
        ('unassigned', 'Pending Driver Assignment'),
        ('accepted', 'Accepted by Driver'),
        ('arrived_store', 'Arrived at Store'),
        ('picked_up', 'Picked Up (In Transit)'),
        ('arrived_customer', 'Arrived at Customer Location'),
        ('delivered', 'Delivered & Completed'),
        ('failed', 'Delivery Failed / Cancelled')
    ], string='Delivery App Status', default='unassigned', tracking=True)

    delivery_signature = fields.Binary(string="Customer Proof Signature", attachment=True)
    delivery_otp = fields.Char(string="OTP", attachment=True)
    cancel_reason = fields.Char(string="Cancel Reason", attachment=True)
    signed_by = fields.Char(string="Receiver Name")
    delivery_latitude = fields.Float(string="Delivery Latitude", digits=(10, 7))
    delivery_longitude = fields.Float(string="Delivery Longitude", digits=(10, 7))



    def send_customer_whatsapp_notification(self, template_name="lbmart_partner_accepted"):
        # 1. Grab metadata in the main thread
        picking_name = self.name
        db_name = self.env.cr.dbname

        customer = self.partner_id
        raw_phone = customer.mobile or customer.phone if customer else False
        if not raw_phone:
            _logger.warning(f"WhatsApp Notification Skipped: No phone number for picking {picking_name}")
            return False

        # Clean phone number (Digits only)
        cleaned_phone = "".join(filter(str.isdigit, str(raw_phone)))
        if len(cleaned_phone) == 10:
            cleaned_phone = f"91{cleaned_phone}"

        # Extract dynamic variable values
        customer_name = customer.name or "Customer"
        order_ref = self.sale_id.name if self.sale_id else picking_name
        driver = self.delivery_driver_id
        driver_name = driver.name if driver else "a delivery partner"
        driver_phone = driver.mobile or driver.phone or "Support"

        # Financials & Delivery Address
        amount_total = f"₹{self.sale_id.amount_total:.2f}" if self.sale_id else "₹0.00"
        payment_mode = "Cash on Delivery" if getattr(self.sale_id, 'is_cod', False) else "Paid Online"
        delivery_address = customer.street or "Denkanikottai"

        # Fetch active Meta WhatsApp configuration
        whatsapp_config = self.env['whatsapp.config'].get_active_config()
        if not whatsapp_config:
            _logger.warning("WhatsApp Notification Skipped: No active 'whatsapp.config' record found.")
            return False

        phone_number_id = whatsapp_config['phone_number_id']
        access_token = whatsapp_config['access_token']
        api_version = whatsapp_config.get('api_version', 'v25.0')

        # 2. Build parameters list based on template stage
        parameters = []

        if template_name == "lbmart_partner_accepted":
            # Template body: Hi {{1}}, partner {{2}} (📞 {{3}}) accepted order {{4}}
            parameters = [
                {"type": "text", "text": str(customer_name)},
                {"type": "text", "text": str(driver_name)},
                {"type": "text", "text": str(driver_phone)},
                {"type": "text", "text": str(order_ref)},
            ]
        elif template_name == "lbmart_partner_reached_store":
            # Template body: Hi {{1}}, partner {{2}} reached store for order {{3}}
            parameters = [
                {"type": "text", "text": str(customer_name)},
                {"type": "text", "text": str(driver_name)},
                {"type": "text", "text": str(order_ref)},
            ]
        elif template_name == "lbmart_out_for_delivery":
            # Template body: Hi {{1}}, order {{2}} is out for delivery with {{3}} (📞 {{4}}), Amount: {{5}}, Address: {{6}}
            parameters = [
                {"type": "text", "text": str(customer_name)},
                {"type": "text", "text": str(order_ref)},
                {"type": "text", "text": str(driver_name)},
                {"type": "text", "text": str(driver_phone)},
                {"type": "text", "text": f"{amount_total} ({payment_mode})"},
                {"type": "text", "text": str(delivery_address)},
            ]
        elif template_name == "lbmart_delivery_nearby":
            # Template body: Hi {{1}}, partner {{2}} is nearby with order {{3}}, Amount: {{4}}
            parameters = [
                {"type": "text", "text": str(customer_name)},
                {"type": "text", "text": str(driver_name)},
                {"type": "text", "text": str(order_ref)},
                {"type": "text", "text": str(amount_total)},
            ]
        elif template_name == "lbmart_order_delivered":
            # Template body: Hi {{1}}, order {{2}} delivered by {{3}}, Status: {{4}}
            parameters = [
                {"type": "text", "text": str(customer_name)},
                {"type": "text", "text": str(order_ref)},
                {"type": "text", "text": str(driver_name)},
                {"type": "text", "text": str(payment_mode)},
            ]
        else:
            # Fallback default 3 parameters
            parameters = [
                {"type": "text", "text": str(customer_name)},
                {"type": "text", "text": str(order_ref)},
                {"type": "text", "text": str(driver_name)},
            ]

        # 3. Define the background worker function
        def _async_send():
            from odoo import api, SUPERUSER_ID
            from odoo.modules.registry import Registry

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
                        "name": template_name,
                        # Meta templates default to "en" for English
                        "language": {"code": "en"},
                        "components": [
                            {
                                "type": "body",
                                "parameters": parameters
                            }
                        ]
                    }
                }

                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=20)
                    if response.status_code in [200, 201]:
                        _logger.info(
                            f"Async WhatsApp [{template_name}] sent successfully to {cleaned_phone} for picking {picking_name}"
                        )
                    else:
                        _logger.error(f"WhatsApp API Error [{response.status_code}]: {response.text}")
                except Exception as e:
                    _logger.error(f"Failed to execute background Meta WhatsApp API call: {str(e)}")

        # 4. Start the background thread
        thread = threading.Thread(target=_async_send)
        thread.daemon = True
        thread.start()
        return True

    def action_assign_driver(self, driver_user_id):
        self.ensure_one()
        if self.delivery_app_status != 'unassigned':
            raise UserError(_("This delivery order has already been accepted by another driver."))

        self.write({
            'delivery_driver_id': driver_user_id,
            'delivery_app_status': 'accepted'
        })
        return True

class ProductCategory(models.Model):
    _inherit = 'product.category'

    image_1920 = fields.Image(
        string='Category Image',
        max_width=1920,
        max_height=1920
    )

class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    image_1920 = fields.Image(
        string='Program Image',
        max_width=1920,
        max_height=1920,
    )