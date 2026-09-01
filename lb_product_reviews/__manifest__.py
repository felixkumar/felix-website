{
    'name': 'LB Product Reviews & Ratings',
    'version': '18.0.1.0.0',
    'category': 'Website/eCommerce',
    'summary': 'Customer product reviews, star ratings and verified purchases for Odoo 18 eCommerce',
    'description': '''Adds product reviews and 1-5 star ratings to the Odoo 18 website shop. Includes moderation, verified purchase detection, helpful votes, rating breakdown, and review images.''',
    'author': 'LB Software Technologies',
    'license': 'LGPL-3',
    'depends': ['website_sale', 'sale_management', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_review_views.xml',
        'views/website_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'lb_product_reviews/static/src/js/product_reviews.js',
            'lb_product_reviews/static/src/scss/product_reviews.scss',
        ],
    },
    'installable': True,
    'application': False,
}
