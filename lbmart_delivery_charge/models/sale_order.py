import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests
import threading
from odoo import models, api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'


    computed_delivery_charge = fields.Float(
        string="Computed Delivery Fee",
        compute="_compute_delivery_charge_amount",
        store=True
    )

    delivery_distance_km = fields.Float(
        string='Delivery Distance (km)',
        readonly=True,
        copy=False
    )

    store_latitude = fields.Float(string="Store Latitude", digits=(10, 7))
    store_longitude = fields.Float(string="Store Longitude", digits=(10, 7))
    customer_latitude = fields.Float(string="Customer Latitude", digits=(10, 7))
    customer_longitude = fields.Float(string="Customer Longitude", digits=(10, 7))

    def action_calculate_distance(self):
        """Button action to fetch driving distance via Google Distance Matrix API."""
        api_key = self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.google_map_api_key')

        if not api_key:
            api_key = "AIzaSyCDt1wcypqjCsDLhTQWnJN2xpPHE4cXxHY"

        if not api_key:
            raise UserError(_("Please configure a valid Google Maps API Key in Settings."))

        for order in self:
            shop_partner = order.warehouse_id.partner_id
            customer_partner = order.partner_shipping_id

            if not shop_partner or not customer_partner:
                raise UserError(_("Ensure both Warehouse and Delivery Address are selected."))

            # Safe address extraction avoiding AttributeError on Many2one fields
            def _format_address(partner):
                parts = [
                    partner.street,
                    partner.street2,
                    partner.city,
                    partner.state_id.name if partner.state_id else False,
                    partner.zip,
                    partner.country_id.name if partner.country_id else False
                ]
                # Filter out None/False/empty strings and join with commas
                return ", ".join([p for p in parts if p])

            origin = _format_address(shop_partner)
            destination = _format_address(customer_partner)

            if not origin or not destination:
                raise UserError(_("Warehouse or Delivery Address lacks sufficient street/city details."))

            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                'origins': origin,
                'destinations': destination,
                'key': api_key,
                'units': 'metric'
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
            }

            try:
                response = requests.get(url, params=params, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()

                if data.get('status') == 'OK':
                    element = data['rows'][0]['elements'][0]
                    element_status = element.get('status')

                    if element_status == 'OK':
                        distance_meters = element['distance']['value']
                        order.delivery_distance_km = round(distance_meters / 1000.0, 2)
                    elif element_status == 'NOT_FOUND':
                        raise UserError(_("Could not geocode one or both addresses. Check street/zip info."))
                    elif element_status == 'ZERO_RESULTS':
                        raise UserError(_("No route found between the warehouse and customer address."))
                    else:
                        raise UserError(_("Distance calculation failed: %s") % element_status)
                else:
                    error_msg = data.get('error_message', data.get('status'))
                    raise UserError(_("Google API Error: %s") % error_msg)

            except requests.exceptions.RequestException as e:
                _logger.error("Failed to connect to Google Distance Matrix API: %s", str(e))
                raise UserError(_("Could not connect to Google Distance Matrix API."))


    @api.depends('order_line.price_subtotal', 'delivery_distance_km')
    def _compute_delivery_charge_amount(self):
        ICPSudo = self.env['ir.config_parameter'].sudo()
        print(',,,,mmm')
        # Minimum Order Threshold
        min_order_val = float(ICPSudo.get_param('lbmart_delivery.min_order_value', 149.0))

        # Distance Tier Parameters
        t1_min = float(ICPSudo.get_param('lbmart_delivery.dist_tier1_min', 0.0))
        t1_max = float(ICPSudo.get_param('lbmart_delivery.dist_tier1_max', 1.0))
        t1_fee = float(ICPSudo.get_param('lbmart_delivery.dist_tier1_fee', 0.0))

        t2_min = float(ICPSudo.get_param('lbmart_delivery.dist_tier2_min', 1.0))
        t2_max = float(ICPSudo.get_param('lbmart_delivery.dist_tier2_max', 3.0))
        t2_fee = float(ICPSudo.get_param('lbmart_delivery.dist_tier2_fee', 25.0))

        t3_min = float(ICPSudo.get_param('lbmart_delivery.dist_tier3_min', 3.0))
        t3_max = float(ICPSudo.get_param('lbmart_delivery.dist_tier3_max', 5.0))
        t3_fee = float(ICPSudo.get_param('lbmart_delivery.dist_tier3_fee', 35.0))

        t4_min = float(ICPSudo.get_param('lbmart_delivery.dist_tier4_min', 5.0))
        t4_max = float(ICPSudo.get_param('lbmart_delivery.dist_tier4_max', 7.0))
        t4_fee = float(ICPSudo.get_param('lbmart_delivery.dist_tier4_fee', 50.0))

        # Free Delivery Subtotal Thresholds
        free_delivery_t2 = float(ICPSudo.get_param('lbmart_delivery.free_delivery_t2', 399.0))
        free_delivery_t3 = float(ICPSudo.get_param('lbmart_delivery.free_delivery_t3', 599.0))
        free_delivery_t4 = float(ICPSudo.get_param('lbmart_delivery.free_delivery_t4', 799.0))

        delivery_product = self.env.ref('lbmart_delivery_charge.product_delivery_charge', raise_if_not_found=False)

        for order in self:
            # Calculate subtotal excluding delivery line
            lines = order.order_line.filtered(
                lambda l: l.product_id != delivery_product) if delivery_product else order.order_line
            subtotal = sum(lines.mapped('price_subtotal'))

            dist = order.delivery_distance_km

            # 1. Zero or negative subtotal check
            if subtotal <= 0:
                order.computed_delivery_charge = 0.0
                continue

            # 2. Check distance tiers
            if t1_min <= dist <= t1_max:
                # 0 - 1 km: Free delivery for all orders (meeting min ₹149)
                order.computed_delivery_charge = t1_fee

            elif t2_min < dist <= t2_max:
                # 1 - 3 km: ₹25 fee, or Free if subtotal >= ₹399
                if subtotal >= free_delivery_t2:
                    order.computed_delivery_charge = 0.0
                else:
                    order.computed_delivery_charge = t2_fee

            elif t3_min < dist <= t3_max:
                # 3 - 5 km: ₹35 fee, or Free if subtotal >= ₹599
                if subtotal >= free_delivery_t3:
                    order.computed_delivery_charge = 0.0
                else:
                    order.computed_delivery_charge = t3_fee

            elif t4_min < dist <= t4_max:
                # 5 - 7 km: ₹50 fee, or Free if subtotal >= ₹799
                if subtotal >= free_delivery_t4:
                    order.computed_delivery_charge = 0.0
                else:
                    order.computed_delivery_charge = t4_fee

            else:
                # Out of range (> 7 km or uncalculated)
                order.computed_delivery_charge = 0.0

    # def action_confirm(self):
    #     # 1. Execute standard confirmation logic first
    #     res = super(SaleOrder, self).action_confirm()
    #
    #     for order in self:
    #         # 2. Check if order can be invoiced
    #         order.action_add_delivery_charge()
    #         if order.invoice_status == 'to invoice':
    #             # 3. Create invoice(s) for the order
    #             invoices = order._create_invoices()
    #
    #             # 4. Post the generated invoice(s)
    #             for invoice in invoices:
    #                 invoice.action_post()
    #
    #     return res

    def action_confirm(self):
        for order in self:
            # 1. Add delivery charge before confirmation so lines and totals update cleanly
            try:
                order.action_add_delivery_charge()
            except Exception as e:
                _logger.warning(f"Failed to add delivery charge for order {order.name}: {str(e)}")

        # 2. Execute standard Odoo confirmation logic
        res = super(SaleOrder, self).action_confirm()

        for order in self:
            # 3. Trigger professional WhatsApp order confirmation asynchronously
            try:
                order.send_order_confirmation_whatsapp()
            except Exception as wa_err:
                _logger.error(f"Failed to trigger confirmation WhatsApp for {order.name}: {str(wa_err)}")

            # 4. Check if order can be invoiced
            if order.invoice_status == 'to invoice':
                try:
                    # 5. Create invoice(s) for the order
                    invoices = order._create_invoices()

                    # 6. Post the generated invoice(s)
                    for invoice in invoices:
                        if invoice.state == 'draft':
                            invoice.action_post()
                except Exception as inv_err:
                    _logger.error(f"Auto-invoice creation/posting failed for order {order.name}: {str(inv_err)}")

        return res

    def send_order_confirmation_whatsapp(self):
        self.ensure_one()
        picking_name = self.name or "SO"
        db_name = self.env.cr.dbname

        customer = self.partner_id
        raw_phone = customer.mobile or customer.phone if customer else False
        if not raw_phone:
            _logger.warning(f"WhatsApp Confirmation Skipped: No phone number for sale order {picking_name}")
            return False

        # Clean phone number (Digits only, add 91 country code if 10 digits)
        cleaned_phone = "".join(filter(str.isdigit, str(raw_phone)))
        if len(cleaned_phone) == 10:
            cleaned_phone = f"91{cleaned_phone}"

        # Strictly sanitize all variables as clean non-empty strings
        customer_name = str(customer.name or "Customer").strip()
        order_ref = str(self.name or "Order").strip()
        amount_total = f"₹{self.amount_total:.2f}" if self.amount_total else "₹0.00"

        is_cod = getattr(self, 'is_cod', False)
        payment_mode = "Cash on Delivery" if is_cod else "Paid Online"
        delivery_address = str(customer.street or "Denkanikottai").strip()

        whatsapp_config = self.env['whatsapp.config'].get_active_config()
        if not whatsapp_config:
            _logger.warning("WhatsApp Notification Skipped: No active 'whatsapp.config' record found.")
            return False

        phone_number_id = whatsapp_config['phone_number_id']
        access_token = whatsapp_config['access_token']
        api_version = whatsapp_config.get('api_version', 'v25.0')

        # Exactly 5 parameters matching lbmart_order_confirmed body variables (en_US)
        parameters = [
            {"type": "text", "text": customer_name},
            {"type": "text", "text": order_ref},
            {"type": "text", "text": amount_total},
            {"type": "text", "text": payment_mode},
            {"type": "text", "text": delivery_address}
        ]

        def _async_send():
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
                        "name": "lbmart_order_confirmed",
                        "language": {"code": "en_US"},
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
                            f"Order Confirmation WhatsApp sent successfully to {cleaned_phone} for order {order_ref}")
                    else:
                        _logger.error(f"WhatsApp API Error [{response.status_code}]: {response.text}")
                        _logger.error(f"Failed Payload: {payload}")
                except Exception as e:
                    _logger.error(f"Failed to execute background WhatsApp API call: {str(e)}")

        thread = threading.Thread(target=_async_send)
        thread.daemon = True
        thread.start()
        return True

    def action_add_delivery_charge(self):
        for order in self:
            company_partner = order.company_id.partner_id
            if company_partner:
                order.write({
                    'store_latitude': company_partner.partner_latitude,
                    'store_longitude': company_partner.partner_longitude,
                })
            # 1. Delivery Charge product
            delivery_product = self.env.ref(
                'lbmart_delivery_charge.product_delivery_charge',
                raise_if_not_found=False
            )

            if delivery_product:
                delivery_line = order.order_line.filtered(
                    lambda line: line.product_id == delivery_product
                )

                if order.computed_delivery_charge == 0.0:
                    if delivery_line:
                        delivery_line.unlink()
                elif delivery_line:
                    delivery_line.write({
                        'price_unit': order.computed_delivery_charge,
                        'product_uom_qty': 1.0,
                    })
                else:
                    self.env['sale.order.line'].create({
                        'order_id': order.id,
                        'product_id': delivery_product.id,
                        'name': 'Delivery Charge',
                        'product_uom_qty': 1.0,
                        'price_unit': order.computed_delivery_charge,
                    })

            # 2. Platform & Packing Fees product
            # 2. Platform & Packing Fees product - search by name
            platform_product = self.env['product.product'].search([
                ('name', '=', 'Platform & Packing Fees')
            ], limit=1)

            if platform_product:
                platform_line = order.order_line.filtered(
                    lambda line: line.product_id == platform_product
                )

                # Use the configured sales price
                platform_fee = platform_product.list_price

                if platform_fee == 0.0:
                    if platform_line:
                        platform_line.unlink()
                elif platform_line:
                    platform_line.write({
                        'price_unit': platform_fee,
                        'product_uom_qty': 1.0,
                    })
                else:
                    self.env['sale.order.line'].create({
                        'order_id': order.id,
                        'product_id': platform_product.id,
                        'name': platform_product.name,
                        'product_uom_qty': 1.0,
                        'price_unit': platform_fee,
                    })

    def write(self, vals):
        res = super(SaleOrder, self).write(vals)
        if 'order_line' in vals:
            for order in self:
                order.sudo().action_add_delivery_charge()
        return res

# class Partner(models.Model):
#     _inherit = 'res.partner'
#
#     latitude = fields.Float(string="Customer Latitude", digits=(10, 7))
#     longitude = fields.Float(string="Customer Longitude", digits=(10, 7))