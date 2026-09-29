import re
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DeliveryPartnerShift(models.Model):
    _name = 'delivery.partner.shift'
    _description = 'Delivery Partner Daily Shift Log'
    _order = 'check_in desc'

    user_id = fields.Many2one(
        'res.users',
        string='Delivery Partner',
        required=True,
        ondelete='cascade',
        index=True,
    )
    check_in = fields.Datetime(string='Check In', required=True, default=fields.Datetime.now)
    check_out = fields.Datetime(string='Check Out')
    duration_hours = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True,
    )
    state = fields.Selection(
        [('open', 'Active Shift'), ('closed', 'Completed')],
        string='Status',
        default='open',
        required=True,
    )

    @api.depends('check_in', 'check_out')
    def _compute_duration(self):
        for record in self:
            if record.check_in and record.check_out:
                delta = record.check_out - record.check_in
                record.duration_hours = round(delta.total_seconds() / 3600.0, 2)
            else:
                record.duration_hours = 0.0

class ResUsers(models.Model):
    _inherit = 'res.users'

    is_delivery_partner = fields.Boolean(string="Is Delivery Partner", default=False)
    is_online = fields.Boolean(string="Is Online", default=False)

    pan_number = fields.Char(string="PAN Card Number")
    aadhaar_number = fields.Char(string="Aadhaar Card Number")
    vehicle_type = fields.Char(string="Vehicle Type")
    vehicle_number = fields.Char(string="Vehicle Number")
    license_number = fields.Char(string="Driving License Number")

    # Document Image Fields
    pan_image = fields.Binary(string="PAN Card Photo", attachment=True)
    aadhaar_front_image = fields.Binary(string="Aadhaar Front Photo", attachment=True)
    aadhaar_back_image = fields.Binary(string="Aadhaar Back Photo", attachment=True)
    license_image = fields.Binary(string="Driving License Photo", attachment=True)

    current_shift_id = fields.Many2one(
        'delivery.partner.shift',
        string='Current Open Shift',
        domain="[('user_id', '=', id), ('state', '=', 'open')]",
    )
    shift_ids = fields.One2many(
        'delivery.partner.shift',
        'user_id',
        string='Shift History',
    )

    @api.constrains('pan_number')
    def _check_pan_number(self):
        pan_regex = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
        for record in self:
            if record.pan_number:
                clean_pan = record.pan_number.strip().upper()
                if not re.match(pan_regex, clean_pan):
                    raise ValidationError("Invalid PAN Card format. Expected format: ABCDE1234F")

    @api.constrains('aadhaar_number')
    def _check_aadhaar_number(self):
        for record in self:
            if record.aadhaar_number:
                clean_aadhaar = re.sub(r'\D', '', record.aadhaar_number)
                if len(clean_aadhaar) != 12:
                    raise ValidationError("Aadhaar Card number must be exactly 12 digits.")
                if record.aadhaar_number != clean_aadhaar:
                    record.aadhaar_number = clean_aadhaar