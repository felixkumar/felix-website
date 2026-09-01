# LB Product Reviews & Ratings — Odoo 18

Custom Odoo 18 module for website eCommerce product reviews and 1–5 star ratings.

## Features
- Customer 1–5 star ratings and review title/body.
- Reviews are moderated: Pending → Approved/Rejected.
- Average rating and rating distribution.
- Verified Purchase badge based on delivered sale order lines.
- Helpful vote counter.
- Sort by recent, helpful, highest, and lowest rating.
- Up to 3 customer photos stored on the review.
- Backend review management with search and filters.
- Responsive frontend section on the standard Odoo product page.

## Dependencies
- website_sale
- sale_management
- portal

## Installation
1. Copy `lb_product_reviews` into an Odoo 18 addons path.
2. Restart Odoo.
3. Update Apps List.
4. Install **LB Product Reviews & Ratings**.
5. Open a website product page and scroll to Customer Reviews & Ratings.
6. Backend reviews are available from Website → Configuration → Product Reviews (menu visibility depends on installed Odoo website menus).

## Notes
- A review submitted by a logged-in customer starts as Pending.
- Verified Purchase is computed from a sale order for the customer's commercial partner where the product has delivered quantity > 0 and the order is confirmed/done.
- Review listing and helpful endpoints use sudo so website visitors can see approved reviews without backend model access.
- If your Odoo 18 database has a heavily customized `website_sale.product` template without `div#product_details`, adjust the XPath in `views/website_templates.xml` to your product page container.
