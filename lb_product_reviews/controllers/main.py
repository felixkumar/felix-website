from odoo import http, _, fields
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
import base64


class LBProductReviews(http.Controller):

    def _stats(self, product):
        Review = request.env['lb.product.review'].sudo()
        reviews = Review.search([
            ('product_tmpl_id', '=', product.id),
            ('state', '=', 'approved'),
            ('active', '=', True),
        ])
        counts = {str(i): 0 for i in range(1, 6)}
        for review in reviews:
            counts[review.rating] += 1
        total = len(reviews)
        average = sum(int(r.rating) for r in reviews) / total if total else 0
        return {'reviews': reviews, 'counts': counts, 'total': total, 'average': average}

    @http.route('/lb_product_reviews/list', type='json', auth='public', website=True)
    def review_list(self, product_id, page=1, sort='recent'):
        product = request.env['product.template'].sudo().browse(int(product_id)).exists()
        if not product:
            return {'error': _('Product not found.')}
        stats = self._stats(product)
        reviews = stats['reviews']
        if sort == 'highest':
            reviews = reviews.sorted(lambda r: (-int(r.rating), r.create_date), reverse=False)
        elif sort == 'lowest':
            reviews = reviews.sorted(lambda r: (int(r.rating), r.create_date), reverse=False)
        elif sort == 'helpful':
            reviews = reviews.sorted(lambda r: (-r.helpful_count, r.create_date), reverse=False)
        else:
            reviews = reviews.sorted(lambda r: r.create_date, reverse=True)
        page = max(1, int(page))
        per_page = 10
        offset = (page - 1) * per_page
        data = []
        for r in reviews[offset:offset + per_page]:
            data.append({
                'id': r.id,
                'title': r.name,
                'rating': int(r.rating),
                'review': r.review,
                'customer': r.partner_id.name or _('Customer'),
                'date': fields.Date.to_string(r.create_date.date()) if r.create_date else '',
                'verified': r.verified_purchase,
                'helpful': r.helpful_count,
            })
        return {'items': data, 'total': stats['total'], 'average': stats['average'], 'counts': stats['counts']}

    @http.route('/lb_product_reviews/submit', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def submit(self, product_id, rating, title, review, **kwargs):
        product = request.env['product.template'].sudo().browse(int(product_id)).exists()
        if not product:
            return request.redirect('/shop')
        vals = {
            'product_tmpl_id': product.id,
            'partner_id': request.env.user.partner_id.id,
            'rating': str(rating),
            'name': (title or '').strip()[:200] or _('Review'),
            'review': (review or '').strip(),
            'state': 'pending',
        }
        for index in range(1, 4):
            upload = kwargs.get('image_%s' % index)
            if upload and getattr(upload, 'read', None):
                vals['image_%s' % index] = base64.b64encode(upload.read())
        try:
            request.env['lb.product.review'].sudo().create(vals)
        except (ValidationError, AccessError):
            return request.redirect('/shop/product/%s?lb_review_error=1#lb-product-reviews' % product.id)
        return request.redirect('/shop/product/%s?lb_review_submitted=1#lb-product-reviews' % product.id)

    @http.route('/lb_product_reviews/helpful/<int:review_id>', type='json', auth='public', website=True, methods=['POST'], csrf=False)
    def helpful(self, review_id):
        review = request.env['lb.product.review'].sudo().browse(review_id).exists()
        if not review or review.state != 'approved' or not review.active:
            return {'error': _('Review not found.')}
        return {'helpful': review.increment_helpful()}
