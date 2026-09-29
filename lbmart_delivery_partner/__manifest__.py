{
    'name': 'LB Mart Delivery Partner Application API',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Backend module and REST APIs for Delivery Driver App integration.',
    'author': 'Felix Kumar / LB Mart',
    'depends': ['stock', 'sale_management','base'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/stock_picking_views.xml',
        'views/delivery_cash_handover_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}