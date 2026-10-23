from odoo import models, fields, api

class WhatsappConfig(models.Model):
    _name = 'whatsapp.config'
    _description = 'Meta WhatsApp API Credentials'

    name = fields.Char(string='Account Name', default='Meta WhatsApp Account', required=True)
    phone_number_id = fields.Char(string='Phone Number ID', required=True)
    access_token = fields.Char(string='Access Token (System/Temp)', required=True)
    api_version = fields.Char(string='API Version', default='v25.0', required=True)
    active = fields.Boolean(default=True)

    @api.model
    def get_active_config(self):
        """Helper method to fetch the active Meta credentials"""
        config = self.sudo().search([('active', '=', True)], limit=1)
        if not config:
            return None
        return {
            'phone_number_id': config.phone_number_id,
            'access_token': config.access_token,
            'api_version': config.api_version
        }