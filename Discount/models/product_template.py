from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    mrp_price = fields.Float(
        string="MRP",
        help="Maximum Retail Price"
    )
    discount_percentage = fields.Float(
        string="Discount (%)",
        default=0.0
    )
    discounted_price = fields.Float(
        string="Discounted Price",
        compute="_compute_discounted_price",
        store=True,
        help="Price calculated automatically after applying discount percentage on MRP"
    )

    @api.depends('list_price', 'discount_percentage')
    def _compute_discounted_price(self):
        for record in self:
            if record.list_price and record.discount_percentage:
                discount_amount = (record.list_price * record.discount_percentage) / 100.0
                record.discounted_price = record.list_price - discount_amount
            else:
                record.discounted_price = record.list_price or 0.0