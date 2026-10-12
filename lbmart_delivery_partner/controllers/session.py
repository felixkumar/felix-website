
from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.session import Session


class LBMartSession(Session):

    @http.route('/web/session/authenticate', type='json', auth='none')
    def authenticate(self, db, login, password,
                     base_location=None, app_type=None):

        # Execute standard Odoo authentication
        result = super().authenticate(
            db=db,
            login=login,
            password=password,
            base_location=base_location,
        )

        print('STEP 1: Original authentication result:', result)
        print('STEP 2: app_type received:', app_type)

        # Check authentication result
        if not isinstance(result, dict) or not result.get('uid'):
            print('STOP: Authentication failed or UID missing')
            return result

        # Get authenticated user
        user = request.env['res.users'].sudo().browse(result['uid'])
        partner = user.partner_id

        print('STEP 3: User ID:', user.id)
        print('STEP 4: Partner ID:', partner.id)

        # Check the field on res.users
        print(
            'STEP 5: Field exists on res.users:',
            'is_delivery_partner' in user._fields
        )

        if 'is_delivery_partner' not in user._fields:
            print('STOP: is_delivery_partner is not loaded on res.users')
            return result

        # Read delivery partner status from res.users
        is_delivery_partner = bool(user.is_delivery_partner)

        print('STEP 6: Is delivery partner:', is_delivery_partner)
        print('STEP 7: app_type:', app_type)

        # Add custom fields to the standard Odoo response
        result.update({
            'is_delivery_partner': is_delivery_partner,
            'user_type': (
                'delivery_partner'
                if is_delivery_partner
                else 'client'
            ),
            'partner_id': partner.id,
            'partner_name': partner.name,
        })

        # Prevent delivery partners from logging into the client app
        if app_type == 'client' and is_delivery_partner:
            request.session.logout(keep_db=True)
            return {
                'uid': False,
                'error': (
                    'This account is registered as a delivery partner. '
                    'Please log in using the Delivery Partner application.'
                ),
            }

        # Prevent customers from logging into the delivery partner app
        if app_type == 'delivery_partner' and not is_delivery_partner:
            request.session.logout(keep_db=True)
            return {
                'uid': False,
                'error': (
                    'This account is registered as a customer. '
                    'Please log in using the Customer application.'
                ),
            }

        print('STEP 8: Authentication completed successfully')
        return result

