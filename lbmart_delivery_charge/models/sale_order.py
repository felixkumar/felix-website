import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

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

    @api.depends('order_line.price_subtotal')
    def _compute_delivery_charge_amount(self):
        ICPSudo = self.env['ir.config_parameter'].sudo()
        tier1_max = float(ICPSudo.get_param('lbmart_delivery.tier1_max', 149.99))
        tier1_fee = float(ICPSudo.get_param('lbmart_delivery.tier1_fee', 30.0))
        tier2_max = float(ICPSudo.get_param('lbmart_delivery.tier2_max', 399.00))
        tier2_fee = float(ICPSudo.get_param('lbmart_delivery.tier2_fee', 25.0))
        delivery_product = self.env.ref('lbmart_delivery_charge.product_delivery_charge', raise_if_not_found=False)

        for order in self:
            lines = order.order_line.filtered(lambda l: l.product_id != delivery_product)
            subtotal = sum(lines.mapped('price_subtotal'))
            if subtotal <= 0:
                order.computed_delivery_charge = 0.0
            elif subtotal < tier1_max:
                order.computed_delivery_charge = tier1_fee
            elif subtotal < tier2_max:
                order.computed_delivery_charge = tier2_fee
            else:
                order.computed_delivery_charge = 0.0

    def action_confirm(self):
        # 1. Execute standard confirmation logic first
        res = super(SaleOrder, self).action_confirm()

        for order in self:
            # 2. Check if order can be invoiced
            order.action_add_delivery_charge()
            if order.invoice_status == 'to invoice':
                # 3. Create invoice(s) for the order
                invoices = order._create_invoices()

                # 4. Post the generated invoice(s)
                for invoice in invoices:
                    invoice.action_post()

        return res

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
