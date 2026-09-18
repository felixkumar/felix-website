from odoo import http, _, fields
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
import base64

from odoo import http
from odoo.http import request

from odoo import http, _
from odoo.http import request


from odoo import http, _
from odoo.http import request


class SaleOrderCouponController(http.Controller):

    @http.route(
        '/api/sale_order/apply_coupon',
        type='json',
        auth='public',
        website=True,
        methods=['POST'],
        csrf=False,
    )
    def apply_coupon(
        self, order_id, coupon_code, discount_amount, product_id=5816
    ):
        """Applies a discount coupon to an active sale order."""
        if not order_id or not coupon_code or discount_amount is None:
            return {
                'status': 'error',
                'message': _('Missing required parameters.'),
            }

        order = request.env['sale.order'].sudo().browse(int(order_id)).exists()
        if not order or order.state not in ['draft', 'sent']:
            return {
                'status': 'error',
                'message': _('Valid draft order not found.'),
            }

        product = (
            request.env['product.product']
            .sudo()
            .browse(int(product_id))
            .exists()
        )
        if not product:
            return {
                'status': 'error',
                'message': _('Discount product configuration missing.'),
            }

        # Remove existing discount line if already applied
        existing_discount = order.order_line.filtered(
            lambda l: l.product_id.id == product.id
        )
        if existing_discount:
            existing_discount.sudo().unlink()

        # Add the new discount line
        discount_price = -abs(float(discount_amount))
        order.sudo().write({
            'order_line': [(
                0,
                0,
                {
                    'product_id': product.id,
                    'product_uom_qty': 1,
                    'price_unit': discount_price,
                    'name': f'Discount - Coupon {coupon_code}',
                },
            )]
        })

        return {
            'status': 'success',
            'order_id': order.id,
            'coupon_code': coupon_code,
            'total_amount': order.amount_total,
            'message': _('Coupon applied successfully.'),
        }

    @http.route(
        '/api/sale_order/remove_coupon',
        type='json',
        auth='public',
        website=True,
        methods=['POST'],
        csrf=False,
    )
    def remove_coupon(self, order_id, product_id=5816):
        """Removes an applied discount coupon from an active sale order."""
        if not order_id:
            return {'status': 'error', 'message': _('Order ID is required.')}

        order = request.env['sale.order'].sudo().browse(int(order_id)).exists()
        if not order or order.state not in ['draft', 'sent']:
            return {
                'status': 'error',
                'message': _('Valid draft order not found.'),
            }

        # Locate and delete matching discount lines
        discount_lines = order.order_line.filtered(
            lambda l: l.product_id.id == int(product_id) or l.price_unit < 0
        )
        if not discount_lines:
            return {
                'status': 'error',
                'message': _('No coupon found on this order.'),
            }

        discount_lines.sudo().unlink()

        return {
            'status': 'success',
            'order_id': order.id,
            'total_amount': order.amount_total,
            'message': _('Coupon removed successfully.'),
        }

class MobileAuthController(http.Controller):

    @http.route('/web/session/authenticate', type='json', auth="none", csrf=False, cors='*')
    def authenticate(self, db, login, password, base_location=None):
        # Perform standard Odoo authentication
        request.session.authenticate(db, login, password)
        
        # Retrieve standard web session metadata
        session_info = request.env['ir.http'].session_info()
        
        # Access authenticated user instance
        user = request.env.user
        
        # Append mobile-specific keys directly into the result payload
        session_info.update({
            'uid': user.id,
            'partner_id': user.partner_id.id if user.partner_id else False,
            'username': user.name,
            'user_email': user.login or user.email,
            'session_id': request.session.sid,
        })
        
        return session_info
class ProductAPI(http.Controller):

    @http.route(
        ["/api/products/top_selling", "/api/products/top_selling/"],
        type="json",
        auth="public",
        methods=["GET", "POST", "OPTIONS"],
        csrf=False,
        cors="*",
    )
    def get_top_selling_products(self, limit=10, **kwargs):
        """Fetches top selling storable and consumable products.

        Uses .sudo() to bypass access restrictions for public endpoints.
        """
        # Parse limit safely if passed as string or inside JSON-RPC params
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 10

        # Step 1: Query sale.report with .sudo() to avoid AccessError
        top_sales = (
            request.env["sale.report"]
            .sudo()
            .read_group(
                domain=[
                    ("state", "in", ["sale", "done"]),
                    ("product_tmpl_id.type", "in", ["consu", "product"]),
                ],
                fields=["product_tmpl_id", "product_uom_qty:sum"],
                groupby=["product_tmpl_id"],
                orderby="product_uom_qty desc",
                limit=limit,
            )
        )

        top_template_ids = [
            item["product_tmpl_id"][0]
            for item in top_sales
            if item.get("product_tmpl_id")
        ]

        if not top_template_ids:
            return {"status": 200, "count": 0, "products": []}

        # Step 2: Fetch full template details using .sudo()
        products = (
            request.env["product.template"].sudo().browse(top_template_ids)
        )

        products_data = products.read(
            [
                "id",
                "name",
                "display_name",
                "list_price",
                "sales_count",
                "qty_available",
                "virtual_available",
                "categ_id",
                "uom_id",
                "image_512",
            ]
        )

        return {
            "status": 200,
            "count": len(products_data),
            "products": products_data,
        }

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
