{
    'name': 'LB Mart Delivery Charge Configuration',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Configurable subtotal-based delivery charges for Sale Orders',
    'author': 'LB Mart',
    'depends': ['sale', 'sales_team', 'base', 'delivery'],
    'data': [
        'data/delivery_product_data.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
