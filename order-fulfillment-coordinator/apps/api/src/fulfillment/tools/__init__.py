from __future__ import annotations

from fulfillment.tools.carriers import get_carrier_rate, list_carriers, shop_rates
from fulfillment.tools.fulfillment import find_nearest_fc, get_fc_capacity, list_fulfillment_centers
from fulfillment.tools.notifications import send_email_notification, send_sms_notification
from fulfillment.tools.analytics import (
    compute_carrier_kpis,
    compute_shipment_stats,
    get_delivery_performance,
)
from fulfillment.tools.integrations import (
    check_odoo_connection,
    create_odoo_sale_order,
    fetch_odoo_products,
    fetch_odoo_sale_orders,
    get_active_odoo_connection,
)

__all__ = [
    "get_carrier_rate",
    "list_carriers",
    "shop_rates",
    "find_nearest_fc",
    "get_fc_capacity",
    "list_fulfillment_centers",
    "send_email_notification",
    "send_sms_notification",
    "compute_carrier_kpis",
    "compute_shipment_stats",
    "get_delivery_performance",
    "get_active_odoo_connection",
    "check_odoo_connection",
    "fetch_odoo_sale_orders",
    "fetch_odoo_products",
    "create_odoo_sale_order",
]
