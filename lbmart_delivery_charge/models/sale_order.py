from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    computed_delivery_charge = fields.Float(
        string="Computed Delivery Fee",
        compute="_compute_delivery_charge_amount",
        store=True
    )

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
            delivery_product = self.env.ref('lbmart_delivery_charge.product_delivery_charge', raise_if_not_found=False)
            if not delivery_product:
                continue
            delivery_line = order.order_line.filtered(lambda l: l.product_id == delivery_product)
            if order.computed_delivery_charge == 0.0:
                if delivery_line:
                    delivery_line.unlink()
                continue
            if delivery_line:
                delivery_line.write({'price_unit': order.computed_delivery_charge, 'product_uom_qty': 1.0})
            else:
                self.env['sale.order.line'].create({
                    'order_id': order.id,
                    'product_id': delivery_product.id,
                    'name': 'Delivery Charge',
                    'product_uom_qty': 1.0,
                    'price_unit': order.computed_delivery_charge,
                })

    def write(self, vals):
        res = super(SaleOrder, self).write(vals)
        if 'order_line' in vals:
            for order in self:
                order.sudo().action_add_delivery_charge()
        return res
