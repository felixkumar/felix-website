import base64
from odoo import http, _, fields
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError


from odoo import http
from odoo.http import request

class SaleCouponAPI(http.Controller):

    @http.route(
        '/api/sale_order/remove_coupon',
        type='json',
        auth='public',
        website=True,
        methods=['POST'],
        csrf=False,
    )
    def remove_coupon(self, order_id=None, product_id=5816, **kwargs):
        """Removes an applied coupon or discount line from a sale order.

        If order_id is not passed, it defaults to the active user's current draft cart.
        """
        # 1. Fetch target order by order_id, or default to the user's active cart
        if order_id:
            order = (
                request.env['sale.order']
                .sudo()
                .browse(int(order_id))
                .exists()
            )
        else:
            order = (
                request.env['sale.order']
                .sudo()
                .search([
                    ('partner_id', '=', request.env.user.partner_id.id),
                    ('state', 'in', ['draft', 'sent']),
                ], limit=1)
            )

        if not order or order.state not in ['draft', 'sent']:
            return {
                'status': 'error',
                'message': _('Valid active draft order not found.'),
            }

        # 2. Locate coupon/discount lines (matching specific product_id OR negative price)
        discount_lines = order.order_line.filtered(
            lambda l: l.product_id.id == int(product_id) or l.price_unit < 0
        )

        if not discount_lines:
            return {
                'status': 'error',
                'message': _('No active coupon found on this order.'),
            }

        # 3. Unlink coupon lines and update order totals
        try:
            discount_lines.sudo().unlink()

            # Recalculate sales order totals
            order._amount_all()

            return {
                'status': 'success',
                'message': _('Coupon removed successfully.'),
                'data': {
                    'order_id': order.id,
                    'order_name': order.name,
                    'subtotal': order.amount_untaxed,
                    'tax': order.amount_tax,
                    'total_amount': order.amount_total,
                },
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to remove coupon: {str(e)}',
            }

    @http.route('/api/cart/apply_coupon', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def apply_coupon(self, promo_code, **kw):
        """
        Validates and applies a coupon/promo code to the current active order.
        Expects JSON payload: {"promo_code": "DISCOUNT10"}
        """
        if not promo_code:
            return {
                'status': 'error',
                'message': 'Coupon code is required.'
            }

        # 1. Fetch the active draft order for the authenticated user
        sale_order = request.env['sale.order'].sudo().search([
            ('partner_id', '=', request.env.user.partner_id.id),
            ('state', 'in', ['draft', 'sent'])
        ], order='id desc', limit=1)

        if not sale_order:
            return {
                'status': 'error',
                'message': 'No active shopping cart/order found.'
            }

        # 2. Search for a valid loyalty card / coupon matching the code
        coupon = request.env['loyalty.card'].sudo().search([
            ('code', '=', promo_code.strip()),
            ('program_id.active', '=', True)
        ], limit=1)

        if not coupon:
            return {
                'status': 'error',
                'message': 'Invalid coupon code.'
            }

        # 3. Validate coupon criteria (expiration, usage limits)
        if coupon.expiration_date and coupon.expiration_date < request.env.cr.now().date():
            return {
                'status': 'error',
                'message': 'This coupon has expired.'
            }

        # 4. Apply coupon reward to the sales order
        try:
            # Odoo 16+ Loyalty Program application hook
            status = sale_order._try_apply_code(promo_code.strip())
            
            if status.get('error'):
                return {
                    'status': 'error',
                    'message': status['error']
                }

            # Recalculate totals after applying discount
            sale_order._amount_all()

            return {
                'status': 'success',
                'message': 'Coupon applied successfully!',
                'data': {
                    'order_id': sale_order.id,
                    'order_name': sale_order.name,
                    'subtotal': sale_order.amount_untaxed,
                    'tax': sale_order.amount_tax,
                    'total': sale_order.amount_total,
                }
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to apply coupon: {str(e)}'
            }


class MobileAuthController(http.Controller):

    @http.route(
        '/web/session/authenticate',
        type='json',
        auth='none',
        csrf=False,
        cors='*',
    )
    def authenticate(self, db, login, password, base_location=None):
        """Authenticates a user session and returns mobile session metadata."""
        request.session.authenticate(db, login, password)
        session_info = request.env['ir.http'].session_info()
        user = request.env.user

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
        """Fetches top selling storable and consumable products."""
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 10

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
        return {
            'reviews': reviews,
            'counts': counts,
            'total': total,
            'average': average,
        }

    @http.route(
        '/lb_product_reviews/list', type='json', auth='public', website=True
    )
    def review_list(self, product_id, page=1, sort='recent'):
        product = (
            request.env['product.template']
            .sudo()
            .browse(int(product_id))
            .exists()
        )
        if not product:
            return {'error': _('Product not found.')}
        stats = self._stats(product)
        reviews = stats['reviews']
        if sort == 'highest':
            reviews = reviews.sorted(
                lambda r: (-int(r.rating), r.create_date), reverse=False
            )
        elif sort == 'lowest':
            reviews = reviews.sorted(
                lambda r: (int(r.rating), r.create_date), reverse=False
            )
        elif sort == 'helpful':
            reviews = reviews.sorted(
                lambda r: (-r.helpful_count, r.create_date), reverse=False
            )
        else:
            reviews = reviews.sorted(lambda r: r.create_date, reverse=True)
        page = max(1, int(page))
        per_page = 10
        offset = (page - 1) * per_page
        data = []
        for r in reviews[offset : offset + per_page]:
            data.append({
                'id': r.id,
                'title': r.name,
                'rating': int(r.rating),
                'review': r.review,
                'customer': r.partner_id.name or _('Customer'),
                'date': fields.Date.to_string(r.create_date.date())
                if r.create_date
                else '',
                'verified': r.verified_purchase,
                'helpful': r.helpful_count,
            })
        return {
            'items': data,
            'total': stats['total'],
            'average': stats['average'],
            'counts': stats['counts'],
        }

    @http.route(
        '/lb_product_reviews/submit',
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def submit(self, product_id, rating, title, review, **kwargs):
        product = (
            request.env['product.template']
            .sudo()
            .browse(int(product_id))
            .exists()
        )
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
            return request.redirect(
                '/shop/product/%s?lb_review_error=1#lb-product-reviews'
                % product.id
            )
        return request.redirect(
            '/shop/product/%s?lb_review_submitted=1#lb-product-reviews'
            % product.id
        )

    @http.route(
        '/lb_product_reviews/helpful/<int:review_id>',
        type='json',
        auth='public',
        website=True,
        methods=['POST'],
        csrf=False,
    )
    def helpful(self, review_id):
        review = (
            request.env['lb.product.review'].sudo().browse(review_id).exists()
        )
        if not review or review.state != 'approved' or not review.active:
            return {'error': _('Review not found.')}
        return {'helpful': review.increment_helpful()}
