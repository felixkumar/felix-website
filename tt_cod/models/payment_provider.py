from odoo import _, api, fields, models
from odoo.osv.expression import OR
from odoo.addons.payment_custom import const

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    custom_mode = fields.Selection(
        selection_add=[('cod', "Cash on Delivery")],
    )

    def _get_default_cod_message(self):
        return _("""
            <div>
                <h5>Cash on Delivery Instructions</h5>
                <p>You will pay when the products are delivered to your address.</p>
                <p>Please ensure you have the exact amount ready for our delivery personnel.</p>
            </div>
        """)

    def action_recompute_pending_msg(self):
        """ Recompute the pending message. """
        for provider in self.filtered(lambda p: p.custom_mode == 'cod'):
            provider.pending_msg = self._get_default_cod_message()
    
    def _transfer_ensure_pending_msg_is_set(self):
        transfer_providers_without_msg = self.filtered(
            lambda p: p.custom_mode == 'cod' and not p.pending_msg
        )
        if transfer_providers_without_msg:
            transfer_providers_without_msg.action_recompute_pending_msg()