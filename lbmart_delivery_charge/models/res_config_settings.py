from odoo import api, fields, models


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
    terms_and_conditions = fields.Html(
        string='Terms & Conditions',
        sanitize=True,
    )
    support_email = fields.Char(
        string='Customer Support Email',
        config_parameter='lbmart_delivery.support_email',
    )

    support_phone = fields.Char(
        string='Customer Support Contact Number',
        config_parameter='lbmart_delivery.support_phone',
    )

    delivery_distance_enabled = fields.Boolean(
        string="Enable Distance-Based Delivery",
        config_parameter="lbmart_delivery.distance_enabled",
        default=False,
    )

    # Tier 1: 0–5 km
    delivery_dist_tier1_min = fields.Float(
        string="Tier 1 Min Distance (km)",
        config_parameter="lbmart_delivery.dist_tier1_min",
        default=0.0,
    )
    delivery_dist_tier1_max = fields.Float(
        string="Tier 1 Max Distance (km)",
        config_parameter="lbmart_delivery.dist_tier1_max",
        default=5.0,
    )
    delivery_dist_tier1_fee = fields.Float(
        string="Tier 1 Fee (₹)",
        config_parameter="lbmart_delivery.dist_tier1_fee",
        default=30.0,
    )

    # Tier 2: Above 5–15 km
    delivery_dist_tier2_min = fields.Float(
        string="Tier 2 Min Distance (km)",
        config_parameter="lbmart_delivery.dist_tier2_min",
        default=5.0,
    )
    delivery_dist_tier2_max = fields.Float(
        string="Tier 2 Max Distance (km)",
        config_parameter="lbmart_delivery.dist_tier2_max",
        default=15.0,
    )
    delivery_dist_tier2_fee = fields.Float(
        string="Tier 2 Fee (₹)",
        config_parameter="lbmart_delivery.dist_tier2_fee",
        default=60.0,
    )

    # Tier 3: Above 15–25 km
    delivery_dist_tier3_min = fields.Float(
        string="Tier 3 Min Distance (km)",
        config_parameter="lbmart_delivery.dist_tier3_min",
        default=15.0,
    )
    delivery_dist_tier3_max = fields.Float(
        string="Tier 3 Max Distance (km)",
        config_parameter="lbmart_delivery.dist_tier3_max",
        default=25.0,
    )
    delivery_dist_tier3_fee = fields.Float(
        string="Tier 3 Fee (₹)",
        config_parameter="lbmart_delivery.dist_tier3_fee",
        default=100.0,
    )

    # Tier 4: Above 25 km
    delivery_dist_tier4_min = fields.Float(
        string="Tier 4 Min Distance (km)",
        config_parameter="lbmart_delivery.dist_tier4_min",
        default=25.0,
    )
    delivery_dist_tier4_max = fields.Float(
        string="Tier 4 Max Distance (km)",
        config_parameter="lbmart_delivery.dist_tier4_max",
        default=999999.0,
    )
    delivery_dist_tier4_fee = fields.Float(
        string="Tier 4 Fee (₹)",
        config_parameter="lbmart_delivery.dist_tier4_fee",
        default=150.0,
    )

    @api.model
    def get_values(self):
        res = super().get_values()

        terms = self.env['ir.config_parameter'].sudo().get_param(
            'lbmart_delivery.terms_and_conditions',
            default=''
        )

        res.update(
            terms_and_conditions=terms,
        )

        return res

    def set_values(self):
        super().set_values()

        self.env['ir.config_parameter'].sudo().set_param(
            'lbmart_delivery.terms_and_conditions',
            self.terms_and_conditions or '',
        )
    
    