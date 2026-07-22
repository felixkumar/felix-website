{
    'name': 'Cash on Delivery (COD) for Odoo',
    'version': '1.0',
    'summary': 'Cash on Delivery Payment Option for Online Store',
    'description': """
        Cash on Delivery (COD) Payment for Odoo eCommerce
        ================================================
        
        This module adds a Cash on Delivery payment option to your Odoo website shop.
        Customers can select COD during checkout and pay when they receive their order.
        
        Features:
        - Adds COD as a payment method in website checkout
        - Skips online payment step for COD orders
        - Fully integrates with Odoo's sales workflow
        - Supports all standard order confirmation and notification processes
        - Easy to configure and enable/disable
        
        Perfect for businesses that want to offer cash payment options to customers.
    """,
    'author': 'Tamayyuz Tijari',
    'company': 'Tamayyuz Tijari',
    'maintainer': 'Tamayyuz Tijari',
    'website': 'https://www.tamayyuz-tijari.com/en/',
    'depends': ['website_sale', 'payment_custom'],
    'data': [
        'views/payment_provider_views.xml',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
    ],
    'images': ['static/description/assets/misc/main_screenshot.png'],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}