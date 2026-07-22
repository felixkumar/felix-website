# Cash on Delivery (COD) for Odoo eCommerce

[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)

This module adds Cash on Delivery (COD) as a payment option for Odoo's eCommerce platform, allowing customers to pay for orders upon delivery.

## Features

- **Seamless Integration**: Works with Odoo's native eCommerce flow
- **Simple Configuration**: Enable/disable with a few clicks
- **Order Processing**: Fully integrated with Odoo's sales order workflow
- **Customer Experience**: Clear COD option during checkout process
- **Compatibility**: Works with Odoo 13.0 and later versions

## Installation

1. Clone this repository or download the module
2. Place the module in your Odoo addons directory
3. Install via Odoo Apps or command line: `./odoo-bin -i payment_cod -d your_database`


## Configuration

1. Go to **Website → Configuration → Payment Providers**
2. Locate "Cash on Delivery" and click on it
3. Configure the settings:
- Set "Journal" to your preferred accounting journal
- Adjust fees if applicable
- Set available countries
4. Click "Save" and then "Enable"

## Usage

For Customers:
1. Add products to cart and proceed to checkout
2. Select "Cash on Delivery" as payment method
3. Complete the order (no online payment required)
4. Pay when the order is delivered

For Merchants:
1. COD orders appear in Sales with "To Invoice" status
2. Process delivery as normal
3. Collect payment upon delivery
4. Register payment in Odoo when received

## Support

This is a community-supported module. For issues or feature requests, please contact us at contact@tamayyuz-tijari.dz.

## License

This module is licensed under LGPL-3, making it free to use, modify, and distribute.

## Contributors

- Tamayyuz Tijari