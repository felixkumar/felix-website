
import logging

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.session import Session

_logger = logging.getLogger(__name__)


class LBMartSession(Session):

    @http.route(
        '/web/session/authenticate',
        type='json',
        auth='none',
    )
    def authenticate(
        self,
        db,
        login,
        password,
        base_location=None,
        app_type=None,
    ):
        """Authenticate the user and validate the requested mobile app."""

        _logger.warning(
            "LBMart authentication controller called. app_type=%s",
            app_type,
        )

        # Preserve standard Odoo authentication
        result = super().authenticate(
            db=db,
            login=login,
            password=password,
            base_location=base_location,
        )

        # Log the authentication result without exposing credentials
        if not isinstance(result, dict):
            _logger.warning(
                "Authentication returned an unexpected response type."
            )
            return result

        uid = result.get('uid')

        _logger.warning(
            "Standard authentication completed. uid=%s",
            uid,
        )

        # Stop if authentication did not produce a valid user ID
        if not uid:
            _logger.warning(
                "Authentication failed or UID is missing."
            )
            return result

        # Retrieve the authenticated user
        user = request.env['res.users'].sudo().browse(uid).exists()

        if not user:
            _logger.warning(
                "Authenticated user record was not found. uid=%s",
                uid,
            )
            return result

        partner = user.partner_id

        _logger.warning(
            "Authenticated user loaded. uid=%s, partner_id=%s",
            user.id,
            partner.id,
        )

        # The field is defined on res.users
        if 'is_delivery_partner' not in user._fields:
            _logger.error(
                "Field is_delivery_partner is not loaded on res.users. "
                "Check the custom field definition and deployed module."
            )
            return result

        is_delivery_partner = bool(user.is_delivery_partner)

        user_type = (
            'delivery_partner'
            if is_delivery_partner
            else 'client'
        )

        _logger.info(
            "User role identified. uid=%s, user_type=%s, app_type=%s",
            user.id,
            user_type,
            app_type,
        )

        # Validate the requested app type
        if app_type not in ('client', 'delivery_partner'):
            _logger.warning(
                "Missing or invalid app_type. uid=%s, app_type=%s",
                user.id,
                app_type,
            )

            request.session.logout(keep_db=True)

            return {
                'uid': False,
                'error': (
                    'Unable to verify the application type. '
                    'Please restart the app and try again.'
                ),
            }

        # Prevent delivery partners from entering the client app
        if app_type == 'client' and is_delivery_partner:
            _logger.warning(
                "Login rejected: delivery partner attempted client app. "
                "uid=%s",
                user.id,
            )

            request.session.logout(keep_db=True)

            return {
                'uid': False,
                'error': (
                    'This account is registered as a delivery partner. '
                    'Please log in using the Delivery Partner application.'
                ),
            }

        # Prevent customers from entering the delivery partner app
        if app_type == 'delivery_partner' and not is_delivery_partner:
            _logger.warning(
                "Login rejected: customer attempted delivery partner app. "
                "uid=%s",
                user.id,
            )

            request.session.logout(keep_db=True)

            return {
                'uid': False,
                'error': (
                    'This account is registered as a customer. '
                    'Please log in using the Customer application.'
                ),
            }

        # Append custom fields while preserving the standard response
        result.update({
            'is_delivery_partner': is_delivery_partner,
            'user_type': user_type,
            'partner_id': partner.id,
            'partner_name': partner.name,
        })

        _logger.info(
            "LBMart authentication completed successfully. "
            "uid=%s, user_type=%s, app_type=%s",
            user.id,
            user_type,
            app_type,
        )

        return result
