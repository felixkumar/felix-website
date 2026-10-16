from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    latitude = fields.Float(
        string="Latitude",
        digits=(10, 7),
        help="Geographic latitude of this contact.",
    )
    longitude = fields.Float(
        string="Longitude",
        digits=(10, 7),
        help="Geographic longitude of this contact.",
    )
