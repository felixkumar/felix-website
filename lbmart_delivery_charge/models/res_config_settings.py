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
    
    