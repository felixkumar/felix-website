from odoo import models, fields, api, _
from odoo.exceptions import UserError


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