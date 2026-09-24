from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    delivery_tier1_max = fields.Float(
        string="Tier 1 Max Subtotal (₹)",
        config_parameter='lbmart_delivery.tier1_max',
        default=150.0,
    )

    delivery_tier1_fee = fields.Float(
        string="Tier 1 Delivery Charge (₹)",
        config_parameter='lbmart_delivery.tier1_fee',
        default=30.0,
    )

    delivery_tier2_max = fields.Float(
        string="Tier 2 Max Subtotal (₹)",
        config_parameter='lbmart_delivery.tier2_max',
        default=400.0,
    )

    delivery_tier2_fee = fields.Float(
        string="Tier 2 Delivery Charge (₹)",
        config_parameter='lbmart_delivery.tier2_fee',
        default=25.0,
    )

    delivery_free_threshold = fields.Float(
        string="Free Delivery Min Subtotal (₹)",
        config_parameter='lbmart_delivery.free_threshold',
        default=400.0,
    )