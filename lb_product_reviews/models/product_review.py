from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class ProductReview(models.Model):
    _name = 'lb.product.review'
    _description = 'LB Product Review'
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Title', required=True, default=lambda self: _('Review'))
    product_tmpl_id = fields.Many2one('product.template', string='Product', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, ondelete='cascade', index=True)
    rating = fields.Selection([
        ('1', '1 Star'), ('2', '2 Stars'), ('3', '3 Stars'), ('4', '4 Stars'), ('5', '5 Stars')
    ], string='Rating', required=True, default='5')
    review = fields.Text(string='Review', required=True)
    state = fields.Selection([
        ('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')
    ], default='pending', required=True, index=True)
    verified_purchase = fields.Boolean(string='Verified Purchase', compute='_compute_verified_purchase', store=True)
    helpful_count = fields.Integer(string='Helpful Votes', default=0)
    active = fields.Boolean(default=True)
    image_1 = fields.Image(string='Photo 1', max_width=1600, max_height=1600)
    image_2 = fields.Image(string='Photo 2', max_width=1600, max_height=1600)
    image_3 = fields.Image(string='Photo 3', max_width=1600, max_height=1600)
    company_id = fields.Many2one('res.company', related='product_tmpl_id.company_id', store=True, readonly=True)

    _sql_constraints = [
        ('rating_valid', 'CHECK (rating IN (\'1\',\'2\',\'3\',\'4\',\'5\'))', 'Rating must be between 1 and 5.'),
    ]

    @api.depends('partner_id', 'product_tmpl_id')
    def _compute_verified_purchase(self):
        SaleLine = self.env['sale.order.line']
        for rec in self:
            if not rec.partner_id or not rec.product_tmpl_id:
                rec.verified_purchase = False
                continue
            domain = [
                ('order_partner_id', 'child_of', rec.partner_id.commercial_partner_id.id),
                ('product_id.product_tmpl_id', '=', rec.product_tmpl_id.id),
                ('order_id.state', 'in', ['sale', 'done']),
                ('qty_delivered', '>', 0),
            ]
            rec.verified_purchase = bool(SaleLine.search_count(domain))

    @api.constrains('review')
    def _check_review(self):
        for rec in self:
            if len((rec.review or '').strip()) < 3:
                raise ValidationError(_('Please enter a review of at least 3 characters.'))

    def action_approve(self):
        self.write({'state': 'approved'})
        return True

    def action_reject(self):
        self.write({'state': 'rejected'})
        return True

    def action_pending(self):
        self.write({'state': 'pending'})
        return True

    def action_toggle_active(self):
        for rec in self:
            rec.active = not rec.active
        return True

    def increment_helpful(self):
        self.sudo().write({'helpful_count': self.helpful_count + 1})
        return self.helpful_count



class ProductTemplate(models.Model):
    _inherit = 'product.template'

    lb_review_ids = fields.One2many(
        'lb.product.review',
        'product_tmpl_id',
        string='Reviews',
    )

    lb_review_count = fields.Integer(
        string='Review Count',
        compute='_compute_lb_review_stats',
    )

    lb_rating_avg = fields.Float(
        string='Average Rating',
        compute='_compute_lb_review_stats',
        digits=(16, 2),
    )

    @api.depends(
        'lb_review_ids.state',
        'lb_review_ids.active',
        'lb_review_ids.rating',
    )
    def _compute_lb_review_stats(self):
        for product in self:
            reviews = product.lb_review_ids.filtered(
                lambda r: r.state == 'approved' and r.active
            )

            product.lb_review_count = len(reviews)

            product.lb_rating_avg = (
                sum(int(review.rating) for review in reviews) / len(reviews)
                if reviews else 0.0
            )
