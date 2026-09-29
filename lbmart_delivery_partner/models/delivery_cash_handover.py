from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DeliveryCashHandover(models.Model):
    _name = 'delivery.cash.handover'
    _description = 'Delivery Person Daily Cash Handover'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Handover Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    user_id = fields.Many2one('res.users', string='Delivery Person', required=True, default=lambda self: self.env.user)
    date = fields.Date(string='Handover Date', required=True, default=fields.Date.context_today)

    line_ids = fields.One2many('delivery.cash.handover.line', 'handover_id', string='Collected Orders')

    total_amount = fields.Monetary(string='Total Cash Handed Over', compute='_compute_total_amount', store=True,
                                   currency_id='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id.id)

    journal_id = fields.Many2one('account.journal', string='Destination Cash Journal', domain=[('type', '=', 'cash')],
                                 required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('confirmed', 'Confirmed & Received'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    note = fields.Text(string='Notes / Discrepancies')

    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(record.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('delivery.cash.handover') or _('New')
        return super().create(vals_list)

    def action_load_todays_cod(self):
        """
        Evening Helper: Automatically pulls all sale orders for this user/driver
        that have posted invoices and were completed/delivered today.
        """
        self.ensure_one()
        if self.state not in ['draft', 'submitted']:
            raise UserError(_("You can only load lines on draft or submitted handover sheets."))

        domain = [
            ('date_order', '>=', fields.Datetime.to_string(fields.Datetime.from_string(self.date))),
            ('date_order', '<=',
             fields.Datetime.to_string(fields.Datetime.from_string(self.date).replace(hour=23, minute=59, second=59))),
            ('state', 'in', ['sale', 'done'])
        ]

        if 'user_id' in self.env['sale.order']._fields:
            domain.append(('user_id', '=', self.user_id.id))

        orders = self.env['sale.order'].search(domain)

        existing_order_ids = self.line_ids.mapped('order_id.id')
        added_count = 0

        for order in orders:
            posted_inv = order.invoice_ids.filtered(
                lambda inv: inv.state == 'posted' and inv.move_type == 'out_invoice')
            if posted_inv and order.id not in existing_order_ids:
                amount_to_collect = posted_inv[0].amount_residual if posted_inv[
                                                                         0].amount_residual > 0 else order.amount_total
                if amount_to_collect > 0:
                    self.env['delivery.cash.handover.line'].create({
                        'handover_id': self.id,
                        'order_id': order.id,
                        'invoice_id': posted_inv[0].id,
                        'amount': amount_to_collect,
                    })
                    added_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Loaded %s COD order(s) for %s.') % (added_count, self.user_id.name),
                'sticky': False,
            }
        }

    def action_submit(self):
        for record in self:
            if not record.line_ids:
                raise UserError(_("Please add at least one order collection line before submitting."))
            record.state = 'submitted'

    def action_confirm(self):
        """Manager confirms physical cash received and completes evening handover"""
        for record in self:
            record.state = 'confirmed'

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class DeliveryCashHandoverLine(models.Model):
    _name = 'delivery.cash.handover.line'
    _description = 'Delivery Cash Handover Line'

    handover_id = fields.Many2one('delivery.cash.handover', string='Handover Reference', ondelete='cascade',
                                  required=True)
    order_id = fields.Many2one('sale.order', string='Sale Order', required=True)

    # Changed from invalid string-filtered related field to a standard Many2one with compute/store
    invoice_id = fields.Many2one('account.move', string='Invoice', compute='_compute_invoice_id', store=True,
                                 readonly=True)

    amount = fields.Monetary(string='Collected Amount', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='handover_id.currency_id', store=True, readonly=True)

    @api.depends('order_id', 'order_id.invoice_ids')
    def _compute_invoice_id(self):
        for line in self:
            if line.order_id:
                posted_inv = line.order_id.invoice_ids.filtered(
                    lambda i: i.state == 'posted' and i.move_type == 'out_invoice')
                line.invoice_id = posted_inv[0] if posted_inv else False
            else:
                line.invoice_id = False

    @api.onchange('order_id')
    def _onchange_order_id(self):
        if self.order_id:
            posted_inv = self.order_id.invoice_ids.filtered(
                lambda i: i.state == 'posted' and i.move_type == 'out_invoice')
            if posted_inv:
                self.invoice_id = posted_inv[0]
                self.amount = posted_inv[0].amount_residual if posted_inv[
                                                                   0].amount_residual > 0 else self.order_id.amount_total
            else:
                self.amount = self.order_id.amount_total